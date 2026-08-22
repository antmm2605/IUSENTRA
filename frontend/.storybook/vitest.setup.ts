import { beforeAll } from 'vitest'
import { installStorybookRuntime } from '../src/stories/storybookRuntime'

beforeAll(() => {
  installStorybookRuntime()
})