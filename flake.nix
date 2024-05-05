{
  description = "alot: Terminal-based Mail User Agent";

  inputs.flake-utils.url = "github:numtide/flake-utils";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.poetry2nix = {
    url = "github:nix-community/poetry2nix";
    inputs.nixpkgs.follows = "nixpkgs";
  };

  outputs = { self, nixpkgs, flake-utils, poetry2nix }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        # see https://github.com/nix-community/poetry2nix/tree/master#api for more functions and examples.
        pkgs = nixpkgs.legacyPackages.${system};
        inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) mkPoetryApplication mkPoetryEnv overrides;
        defaultArgs = {
          projectDir = self;
          overrides = overrides.withDefaults (final: prev: {
            gpg = prev.gpgme;
            notmuch2 = pkgs.python3.pkgs.notmuch2;
          });
        };
      in
      {
        packages = {
          alot = mkPoetryApplication (defaultArgs // {
            nativeBuildInputs = [
              pkgs.python3.pkgs.cffi
            ];
            propagatedBuildInputs = with pkgs; [
              gpgme
              pkgs.gpgme.dev
              pkgs.python3.pkgs.cffi
            ];

            nativeCheckInputs = with pkgs; [ gnupg notmuch procps ];
            checkPhase = ''
              # In the nix sandbox stdin is not a terminal but /dev/null so we
              # change the shell command only in this specific test.
              sed -i '/test_no_spawn_no_stdin_attached/,/^$/s/test -t 0/sh -c "[ $(wc -l) -eq 0 ]"/' tests/commands/test_global.py

              python3 -m unittest -v
            '';
          });
          docs = pkgs.runCommand "alot-docs" {
            src = self;
            nativeBuildInputs = [
              (mkPoetryEnv (defaultArgs // { groups = ["doc"]; }))
              pkgs.gnumake
            ];
          } ''make -C $src/docs html man BUILDDIR=$out'';
          default = self.packages.${system}.alot;
        };
      });
}
