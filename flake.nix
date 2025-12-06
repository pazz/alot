{
  description = "alot: Terminal-based Mail User Agent";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.pyproject-nix.url = "github:pyproject-nix/pyproject.nix";
  inputs.pyproject-nix.inputs.nixpkgs.follows = "nixpkgs";
  inputs.systems.url = "github:nix-systems/default";

  outputs = {
    self,
    nixpkgs,
    pyproject-nix,
    systems,
  }: let
    project = pyproject-nix.lib.project.loadPyproject {projectRoot = ./.;};
    eachSystem = nixpkgs.lib.genAttrs (import systems);
    # the package is called gpg on PyPI and gpgme in nixpkgs
    packageOverrides = final: prev: {gpg = final.gpgme;};
  in {
    packages = eachSystem (system: let
      pkgs = nixpkgs.legacyPackages.${system};
      python3 = pkgs.python3;
      # let pyproject-nix generate the argument for buildPythonApplication
      # from our pyproject.toml file
      attrs = project.renderers.buildPythonPackage {
        python = python3.override {inherit packageOverrides;};
      };
      # overwrite these attributes in the buildPythonApplication call
      overrides = {
        version = "0.dev+${self.shortRev or self.dirtyShortRev}";
        outputs = ["out" "doc" "man"];
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
        nativeCheckInputs = with pkgs; [gnupg notmuch procps];
        nativeBuildInputs = [python3.pkgs.sphinxHook pkgs.installShellFiles];
        sphinxBuilders = ["html" "man"];
      };
    in {
      alot = python3.pkgs.buildPythonApplication (attrs // overrides);
      docs =
        pkgs.lib.trivial.warn "The docs attribute moved to alot.doc"
        self.packages.${system}.alot.doc;
      default = self.packages.${system}.alot;
    });
    devShells = eachSystem (system: let
      pkgs = nixpkgs.legacyPackages.${system};
      arg = project.renderers.withPackages {
        python = pkgs.python3.override {inherit packageOverrides;};
        extras = builtins.attrNames project.dependencies.extras;
        extraPackages = ps: [ps.twine ps.build];
      };
      pythonEnv = pkgs.python3.withPackages arg;
    in {
      default = pkgs.mkShell {packages = [pythonEnv];};
    });
    checks = eachSystem (system: let
      pkgs = nixpkgs.legacyPackages.${system};

      arg = project.renderers.withPackages {
        python = pkgs.python3.override {inherit packageOverrides;};
        extras = ["typing"];
      };
      pythonEnv = pkgs.python3.withPackages arg;
    in {
      alot = self.packages.${system}.alot;
      types = pkgs.runCommand "alot-type-check" {buildInputs = [pythonEnv];} ''
        cd ${self}
        mypy --ignore-missing-imports alot/errors.py alot/__init__.py alot/utils/cached_property.py
        touch $out
      '';
    });
  };
}
