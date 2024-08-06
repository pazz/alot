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
        # extract the python dependencies from the pyprojec file, cut the version constraint
        dependencies' = pkgs.lib.lists.concatMap (builtins.match "([^>=<]*).*") pyproject.project.dependencies;
        # the package is called gpg on PyPI but gpgme in nixpkgs
        dependencies = map (x: if x == "gpg" then "gpgme" else x) dependencies';
      in
      {
        packages = {
          alot = pkgs.python3Packages.buildPythonApplication {
            name = "alot";
            version = pyproject.project.version + "-post";
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
              # In the nix sandbox stdin is not a terminal but /dev/null so we
              # change the shell command only in this specific test.
              sed -i '/test_no_spawn_no_stdin_attached/,/^$/s/test -t 0/sh -c "[ $(wc -l) -eq 0 ]"/' tests/commands/test_global.py

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
