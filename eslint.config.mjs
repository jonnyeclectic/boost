// ESLint for the theme's one JS asset (style/boost.js — cursor glow + scroll
// reveal). Correctness rules only: undefined globals, unused vars, loose
// equality, legacy `var`. The file is plain-script browser JS, no build step.
export default [
  {
    files: ["style/**/*.js"],
    languageOptions: {
      ecmaVersion: 2021,
      sourceType: "script",
      globals: {
        window: "readonly",
        document: "readonly",
        IntersectionObserver: "readonly",
        requestAnimationFrame: "readonly",
      },
    },
    rules: {
      "no-undef": "error",
      "no-unused-vars": "error",
      "eqeqeq": "error",
      "no-var": "error",
    },
  },
];
