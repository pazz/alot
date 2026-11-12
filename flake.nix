{
  description = "alot: Terminal-based Mail User Agent";

  inputs.nixpkgs.url = "https://channels.nixos.org/nixpkgs-unstable/nixexprs.tar.zst";
  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.flake-utils.inputs.systems.follows = "systems";
  inputs.pyproject-nix.url = "github:pyproject-nix/pyproject.nix";
  inputs.pyproject-nix.inputs.nixpkgs.follows = "nixpkgs";
  inputs.systems.url = "github:nix-systems/default";

  outputs = {
    self,
    nixpkgs,
    flake-utils,
    pyproject-nix,
    ...
  }: let
    project = pyproject-nix.lib.project.loadPyproject {projectRoot = ./.;};
    version = "0.dev+" + self.shortRev or self.dirtyShortRev or "override";
  in
    flake-utils.lib.eachDefaultSystem (system: let
      pkgs = import nixpkgs {inherit system;};
      python = pkgs.python3;
      # let pyproject-nix generate the argument for buildPythonApplication
      # from our pyproject.toml file
      attrs = project.renderers.buildPythonPackage {inherit python;};
      # overwrite these attributes in the buildPythonApplication call
      overrides = {
        inherit version;
        outputs = ["out" "doc" "man"];
        postPatch = ''
          substituteInPlace alot/settings/theme.py \
            --replace-fail /usr/share "$out/share"
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
        nativeCheckInputs = with pkgs; [gnupg notmuch procps];
        nativeBuildInputs = [python.pkgs.sphinxHook pkgs.installShellFiles];
        sphinxBuilders = ["html" "man"];
      };
      alot-pkg = python.pkgs.buildPythonPackage (attrs // overrides);
      alot-app = python.pkgs.toPythonApplication alot-pkg;
      pythonEnv = renderArgs: python.withPackages (
        project.renderers.withPackages (renderArgs // {inherit python;})
      );
      devEnv = pythonEnv {
        extras = builtins.attrNames project.dependencies.extras;
        extraPackages = ps: [ps.twine ps.build];
      };
      typingEnv = pythonEnv {extras = ["typing"];};
    in {
      packages = {
        alot = alot-app;
        default = alot-app;
        theme-test = pkgs.runCommand "theme-test.py" {
          propagatedBuildInputs = [
            (python.withPackages (ps: [alot-pkg]))
          ];
        } ''
          install -Dm755 ${./extra/theme_test.py} $out/bin/theme-test.py
          patchShebangs $out/bin
        '';
      };
      devShells.default = pkgs.mkShell {packages = [devEnv];};
      checks = {
        alot = self.packages.${system}.alot;
        types = pkgs.runCommand "alot-type-check" {buildInputs = [typingEnv];} ''
          cd ${self}
          mypy --cache-dir=/dev/null --ignore-missing-imports \
            alot/__init__.py \
            alot/account.py \
            alot/crypto.py \
            alot/db \
            alot/errors.py \
            alot/helper.py \

          touch $out
        '';
      };
    }
  );
}
