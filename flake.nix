{
  description = "CPU & memory plotter for two processes";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs = { self, nixpkgs }:
    let
      forAllSystems = nixpkgs.lib.genAttrs [
        "x86_64-linux"
        "aarch64-linux"
        "x86_64-darwin"
        "aarch64-darwin"
      ];
    in
    {
      devShells = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python3.withPackages (ps: [ ps.matplotlib ]);
        in
        {
          default = pkgs.mkShell {
            packages = [ python ];
          };
        }
      );

      packages = forAllSystems (system:
        let
          pkgs = nixpkgs.legacyPackages.${system};
          python = pkgs.python3.withPackages (ps: [ ps.matplotlib ]);
        in
        {
          default = pkgs.writeShellScriptBin "cpu-mem-plot" ''
            exec ${python}/bin/python3 ${./main.py} "$@"
          '';
        }
      );
    };
}
