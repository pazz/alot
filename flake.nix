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
        inherit (poetry2nix.lib.mkPoetry2Nix { inherit pkgs; }) mkPoetryApplication overrides;
      in
      {
        packages = {
          alot = mkPoetryApplication {
            projectDir = self;
            nativeBuildInputs = [
              pkgs.python3.pkgs.cffi
            ];
            propagatedBuildInputs = with pkgs; [
              gpgme
              pkgs.gpgme.dev
              pkgs.python3.pkgs.cffi
            ];
            overrides = overrides.withDefaults (final: prev: {
              gpg = prev.gpgme;
              notmuch2 = pkgs.python3.pkgs.notmuch2;
            });

            nativeCheckInputs = with pkgs; [ gnupg notmuch procps ];
            checkPhase = "python3 -m unittest -v";
          };
          default = self.packages.${system}.alot;
        };
      });
}
