import type { ReactElement } from 'react'
import type { StoryObj } from '@storybook/react-vite'

import { AppProviders } from '../app/providers'
import { installStorybookRuntime } from './storybookRuntime'

type PageStoryOptions = {
  sourcePath: string
  title: string
  render: () => ReactElement
}

export type IusentraPageStory = StoryObj

export function createPageStory({ sourcePath, title, render }: PageStoryOptions): IusentraPageStory {
  return {
    name: title,
    parameters: {
      iusentraPage: true,
      sourcePath,
    },
    render: () => {
      installStorybookRuntime()
      return (
        <AppProviders>
          <div data-storybook-source={sourcePath}>{render()}</div>
        </AppProviders>
      )
    },
  }
}
