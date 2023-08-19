{
  description = "Application packaged using poetry2nix";

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
        inherit (poetry2nix.legacyPackages.${system}) mkPoetryApplication;
        pkgs = nixpkgs.legacyPackages.${system};

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
            overrides = poetry2nix.legacyPackages.${system}.overrides.withDefaults (final: prev: {
              gpg = prev.gpgme;
              notmuch2 = pkgs.python3.pkgs.notmuch2;
            });

          };
          default = self.packages.${system}.alot;
        };
      });
}
