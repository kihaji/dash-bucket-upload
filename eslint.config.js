const js = require('@eslint/js');
const babelParser = require('@babel/eslint-parser');
const reactPlugin = require('eslint-plugin-react');
const importPlugin = require('eslint-plugin-import');
const reactHooksPlugin = require('eslint-plugin-react-hooks');
const prettier = require('eslint-config-prettier');
const globals = require('globals');

module.exports = [
    {ignores: ['**/*.css', '**/registerServiceWorker.js']},
    js.configs.recommended,
    {
        files: ['src/**/*.{js,jsx}'],
        languageOptions: {
            parser: babelParser,
            parserOptions: {
                sourceType: 'module',
                requireConfigFile: true,
                ecmaFeatures: {jsx: true},
            },
            globals: {
                ...globals.browser,
                ...globals.node,
                ...globals.jest,
                ...globals.jasmine,
            },
        },
        plugins: {
            react: reactPlugin,
            'react-hooks': reactHooksPlugin,
            import: importPlugin,
        },
        settings: {
            react: {version: 'detect'},
            // Don't Babel-parse installed packages (no babel config applies there)
            'import/ignore': ['node_modules'],
        },
        rules: {
            'accessor-pairs': ['error'],
            'block-scoped-var': ['error'],
            'consistent-return': ['error'],
            'curly': ['error', 'all'],
            'default-case': ['error'],
            'dot-notation': ['error'],
            'eqeqeq': ['error', 'always', {null: 'ignore'}],
            'import/no-duplicates': ['error'],
            'import/no-named-as-default': ['error'],
            'new-cap': ['error'],
            'no-alert': ['warn'],
            'no-caller': ['error'],
            'no-case-declarations': ['error'],
            'no-console': ['off'],
            'no-div-regex': ['error'],
            'no-dupe-keys': ['error'],
            'no-else-return': ['error'],
            'no-empty-pattern': ['error'],
            // `x == null` / `!= null` (null-or-undefined) and passing `undefined` for
            // optional props are deliberate idioms throughout this codebase.
            'no-eq-null': ['off'],
            'no-eval': ['error'],
            'no-extend-native': ['error'],
            'no-extra-bind': ['error'],
            'no-extra-boolean-cast': ['error'],
            'no-implicit-coercion': ['error'],
            'no-implied-eval': ['error'],
            'no-inner-declarations': ['off'],
            'no-invalid-this': ['error'],
            'no-iterator': ['error'],
            'no-labels': ['error'],
            'no-lone-blocks': ['error'],
            'no-loop-func': ['error'],
            'no-multi-str': ['error'],
            'no-global-assign': ['error'],
            'no-new': ['error'],
            'no-new-func': ['error'],
            'no-new-wrappers': ['error'],
            'no-param-reassign': ['error'],
            'no-process-env': ['warn'],
            'no-proto': ['error'],
            'no-redeclare': ['error'],
            'no-return-assign': ['error'],
            'no-script-url': ['error'],
            'no-self-compare': ['error'],
            'no-sequences': ['error'],
            'no-shadow': ['off'],
            'no-throw-literal': ['error'],
            'no-undefined': ['off'],
            'no-unused-expressions': ['error'],
            'no-use-before-define': ['error', 'nofunc'],
            'no-useless-call': ['error'],
            'no-useless-concat': ['error'],
            'no-with': ['error'],
            'radix': ['error'],
            'react/jsx-no-duplicate-props': ['error'],
            'react/jsx-no-undef': ['error'],
            'react/jsx-uses-react': ['error'],
            'react/jsx-uses-vars': ['error'],
            'react/no-did-update-set-state': ['error'],
            'react/no-direct-mutation-state': ['error'],
            'react/no-is-mounted': ['error'],
            'react/no-unknown-property': ['error'],
            'react/prefer-es6-class': ['error', 'always'],
            'react/prop-types': 'error',
            // Statically enforces what bug #9 violated (hooks after an early return)
            'react-hooks/rules-of-hooks': 'error',
            'react-hooks/exhaustive-deps': 'off',  // effects here deliberately use refs to avoid re-subscribing

            'yoda': ['error'],
            'spaced-comment': ['error', 'always', {block: {exceptions: ['*']}}],
            'no-unused-vars': ['error', {
                args: 'after-used',
                argsIgnorePattern: '^_',
                caughtErrorsIgnorePattern: '^e$',
            }],
            // Deliberately omitted from the legacy config port: no-magic-numbers and
            // no-inline-comments — WebGL/geo code is full of coordinate, color, and
            // shader constants where extracting names hurts readability.
            'no-underscore-dangle': ['off'],
        },
    },
    prettier,
];
