import type { Preview } from '@storybook/react-vite'

import '../src/index.css'
import '../src/styles/iusentra-design-system.css'
import '../src/stories/storybook.css'
import { installStorybookRuntime } from '../src/stories/storybookRuntime'

installStorybookRuntime()

const preview: Preview = {
  parameters: {
    a11y: {
      test: 'error',
    },
    controls: {
      expanded: true,
    },
  },
  decorators: [
    (Story, context) => (
      <div className={context.parameters?.iusentraPage ? 'ius-storybook-page-canvas' : 'ius-storybook-component-canvas'}>
        <Story />
      </div>
    ),
  ],
}

export default preview
