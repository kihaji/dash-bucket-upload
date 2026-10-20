import { transformAsync } from '@babel/core';
import { defineConfig } from 'vitest/config';

// Component sources are .js files containing JSX (the dash-generate-components
// convention), which Vite's parser rejects. Compile JSX with the project's
// Babel React preset first; module syntax is left for Vite.
const jsxInJs = {
    name: 'jsx-in-js',
    enforce: 'pre',
    async transform(code, id) {
        if (!/\/src\/lib\/.*\.js$/.test(id) || !code.includes('<')) {
            return null;
        }
        const result = await transformAsync(code, {
            filename: id,
            babelrc: false,
            configFile: false,
            presets: ['@babel/preset-react'],
            sourceMaps: true,
        });
        return { code: result.code, map: result.map };
    },
};

export default defineConfig({
    plugins: [jsxInJs],
});
