import vue from 'eslint-plugin-vue'
import globals from 'globals'
export default [
  ...vue.configs['flat/recommended'],
  { files: ['frontend/**/*.{js,vue}'], languageOptions: { globals: { ...globals.browser, ...globals.node } },
    rules: { 'vue/multi-word-component-names': 'off', 'vue/max-attributes-per-line': 'off',
      'vue/singleline-html-element-content-newline': 'off', 'vue/html-self-closing': 'off' } },
]
