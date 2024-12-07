{
  description = "alot: Terminal-based Mail User Agent";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        # we want to extract some metadata and especially the dependencies
        # from the pyproject file, like this we do not have to maintain the
        # list a second time
        pyproject = pkgs.lib.trivial.importTOML ./pyproject.toml;
        # get a list of python packages by name, used to get the nix packages
        # for the dependency names from the pyproject file
        getPkgs = names: builtins.attrValues (pkgs.lib.attrsets.getAttrs names pkgs.python3Packages);
        # extract the python dependencies from the pyprojec file, cut the version constraints
        dependencies' = pkgs.lib.lists.concatMap (builtins.match "([^>=<;]*).*") pyproject.project.dependencies;
        # the package is called gpg on PyPI but gpgme in nixpkgs
        renameGPG = x: if x == "gpg" then "gpgme" else x;
        # mailcap has been removed from the stdlib in py3.13 and needs to be
        # fetched from pypi
        withMailcap = x: (pkgs.lib.strings.versionOlder "3.12" pkgs.python3.version) || (x != "standard-mailcap");
        dependencies = map renameGPG (builtins.filter withMailcap dependencies');
      in
      {
        packages = {
          alot = pkgs.python3Packages.buildPythonApplication {
            name = "alot";
            version = "0.dev+${if self ? shortRev then self.shortRev else "dirty"}";
            src = self;
            pyproject = true;
            outputs = [
              "out"
              "doc"
              "man"
            ];
            build-system = getPkgs pyproject."build-system".requires;
            dependencies = getPkgs dependencies;
            postPatch = ''
              substituteInPlace alot/settings/manager.py \
                --replace /usr/share "$out/share"
            '';
            postInstall = ''
              installShellCompletion --zsh --name _alot extra/completion/alot-completion.zsh
              mkdir -p $out/share/{applications,alot}
              cp -r extra/themes $out/share/alot
              sed "s,/usr/bin,$out/bin,g" extra/alot.desktop > $out/share/applications/alot.desktop
            '';
            checkPhase = ''
              python3 -m unittest -v
            '';
            nativeCheckInputs = with pkgs; [ gnupg notmuch procps ];
            nativeBuildInputs = with pkgs; [
              python3Packages.sphinxHook
              installShellFiles
            ];
            sphinxBuilders = [ "html" "man" ];
          };
          docs = pkgs.lib.trivial.warn "The docs attribute moved to alot.doc"
            self.packages.${system}.alot.doc;
          default = self.packages.${system}.alot;
        };
      });
}
