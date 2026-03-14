import antfu from "@antfu/eslint-config";

const config = antfu({
  rules: {
    "no-console": "off",
    "no-use-before-define": ["off"],
    "antfu/top-level-function": "off",
    "array-callback-return": ["off"],
    "style/brace-style": ["error", "1tbs"],
    "style/arrow-parens": ["error", "always"],
    "unused-imports/no-unused-vars": "warn",
    "unused-imports/no-unused-imports": "warn",
    "perfectionist/sort-imports": ["warn", {
      type: "natural",
      order: "asc",
      groups: [
        "builtin",
        "external",
        "internal",
        "parent",
        "sibling",
        "index",
        "object",
        "type",
        "unknown",
      ],
      newlinesBetween: "always",
      internalPattern: ["^@/", "^@components/", "^@views/", "^@utils/", "^@stores/", "^@api/", "^@assets/"],
    }],
    "node/prefer-global/process": ["off"],
    "ts/no-use-before-define": ["off"],
    "ts/array-callback-return": ["off"],
    "ts/no-namespace": ["warn", {
      allowDeclarations: true,
      allowDefinitionFiles: true,
    }],
    "vue/block-order": [
      "error",
      {
        order: [
          "template",
          "script:not([setup])",
          "script[setup]",
          "style:not([scoped])",
          "style[scoped]",
        ],
      },
    ],
    "vue/singleline-html-element-content-newline": ["off"],
    "vue/attribute-hyphenation": ["error", "always"],
    "vue/max-attributes-per-line": [
      "error",
      {
        singleline: {
          max: 10,
        },
        multiline: {
          max: 1,
        },
      },
    ],
    "vue/attributes-order": [
      "error",
      {
        order: [
          "GLOBAL",
          "DEFINITION",
          "LIST_RENDERING",
          ["UNIQUE", "SLOT"],
          "RENDER_MODIFIERS",
          "CONDITIONALS",
          "OTHER_DIRECTIVES",
          "ATTR_SHORTHAND_BOOL",
          "ATTR_STATIC",
          "TWO_WAY_BINDING",
          "ATTR_DYNAMIC",
          "EVENTS",
          "CONTENT",
        ],
        alphabetical: true,
      },
    ],
    "vue/html-self-closing": [
      "error",
      {
        html: {
          void: "never",
          normal: "never",
          component: "never",
        },
        svg: "always",
        math: "always",
      },
    ],
  },
  ignores: [
    "android/**",
    "package.json",
    "tsconfig.json",
    "tsconfig.*.json",
  ],
  stylistic: {
    indent: 2, // 4, or 'tab'
    quotes: "double", // or 'single'
    semi: true,
  },
  typescript: true,
  vue: {
    overrides: {
      "vue/no-empty-pattern": ["error", {
        allowObjectPatternsAsParameters: true,
      }],
    },
  },
});

export default config;
