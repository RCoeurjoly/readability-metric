{
  description = "Readability metrics for EPUB books";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python312;
        pythonPackages = python.pkgs;

        readabilityMetric = pythonPackages.buildPythonApplication {
          pname = "readability-metric";
          version = "0.2.0";
          pyproject = true;
          src = ./.;

          build-system = with pythonPackages; [
            setuptools
            wheel
          ];

          dependencies = with pythonPackages; [
            beautifulsoup4
            ebooklib
            langdetect
            lxml
            numpy
            pymongo
            scipy
          ];

          pythonImportsCheck = [
            "readability_metric"
            "corpus_analysis"
          ];
        };

        devPython = python.withPackages (
          ps: with ps; [
            beautifulsoup4
            ebooklib
            langdetect
            lxml
            numpy
            pymongo
            scipy
          ]
        );
      in
      {
        packages.default = readabilityMetric;
        packages.readability-metric = readabilityMetric;

        apps.default = flake-utils.lib.mkApp {
          drv = readabilityMetric;
          exePath = "/bin/readability-metric";
        };

        devShells.default = pkgs.mkShell {
          packages = [
            devPython
            pkgs.mongodb-tools
            pkgs.ruff
          ];
        };

        formatter = pkgs.nixfmt;
      }
    );
}
