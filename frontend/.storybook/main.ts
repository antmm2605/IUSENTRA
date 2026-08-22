import type { StorybookConfig } from '@storybook/react-vite'

const config: StorybookConfig = {
  stories: [
    '../src/**/*.stories.@(ts|tsx)',
    '../../packages/ui/src/**/*.stories.@(ts|tsx)',
  ],
  addons: ['@storybook/addon-a11y', '@storybook/addon-docs', '@storybook/addon-vitest'],
  framework: {
    name: '@storybook/react-vite',
    options: {},
  },
  docs: {
    autodocs: 'tag',
  },
  async viteFinal(config) {
    config.base = './'
    config.plugins = config.plugins?.filter((plugin) => (
      plugin?.name !== 'iusentra-prune-react-assets'
      && plugin?.name !== 'iusentra-enforce-bundle-budget'
      && plugin?.name !== 'iusentra-sanitize-generated-text'
    ))
    return config
  },
}

export default config
