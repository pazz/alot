{
  description = "alot: Terminal-based Mail User Agent";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
      in
      {
        packages = {
          alot = pkgs.python3Packages.buildPythonApplication {
            name = "alot";
            version = "dev";
            src = self;
            pyproject = true;
            outputs = [
              "out"
              "doc"
              "man"
            ];
            build-system = with pkgs.python3Packages; [
              setuptools
              setuptools-scm
            ];
            dependencies = with pkgs.python3Packages; [
              configobj
              gpgme
              notmuch2
              python-magic
              twisted
              urwid
              urwidtrees
            ];
            checkPhase = ''
              # In the nix sandbox stdin is not a terminal but /dev/null so we
              # change the shell command only in this specific test.
              sed -i '/test_no_spawn_no_stdin_attached/,/^$/s/test -t 0/sh -c "[ $(wc -l) -eq 0 ]"/' tests/commands/test_global.py

              python3 -m unittest -v
            '';
            nativeCheckInputs = with pkgs; [ gnupg notmuch procps ];
            nativeBuildInputs = with pkgs.python3Packages; [ sphinxHook ];
            sphinxBuilders = [ "html" "man" ];
          };
          docs = pkgs.lib.trivial.warn "The docs attribute moved to alot.doc"
            self.packages.${system}.alot.doc;
          default = self.packages.${system}.alot;
        };
      });
}
