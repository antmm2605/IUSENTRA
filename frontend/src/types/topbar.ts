export type TopbarEntityType =
  | 'case'
  | 'client'
  | 'matter'
  | 'deadline'
  | 'hearing'
  | 'document'
  | 'activity'
  | 'communication'
  | 'invoice'

export type TopbarPriority = 'normal' | 'important' | 'urgent'

export type GlobalSearchResult = {
  id: string
  type: TopbarEntityType
  title: string
  subtitle: string | null
  description: string | null
  href: string
  priority: TopbarPriority
  metadata: {
    clientName: string | null
    caseNumber: string | null
    date: string | null
    status: string | null
  }
}

export type GlobalSearchPayload = {
  ok: boolean
  query: string
  total: number
  results: GlobalSearchResult[]
  groups?: Array<{ type: TopbarEntityType; items: GlobalSearchResult[] }>
}

export type TopbarTodayItem = {
  id: string
  type: 'hearing' | 'deadline' | 'task' | 'appointment' | 'communication'
  title: string
  time: string | null
  date: string
  priority: TopbarPriority
  href: string
  caseId: string | null
  clientName: string | null
  status: string | null
}

export type TopbarTodayPayload = {
  ok: boolean
  date: string
  summary: {
    hearingsToday: number
    deadlinesToday: number
    tasksToday: number
    urgentItems: number
    unreadCommunications: number
  }
  items: TopbarTodayItem[]
}

export type TopbarNotification = {
  id: string
  type: 'deadline' | 'hearing' | 'task' | 'communication' | 'filing' | 'invoice' | 'document'
  title: string
  message: string
  createdAt: string
  priority: TopbarPriority
  read: boolean
  href: string | null
  actionLabel: string | null
}

export type TopbarNotificationsPayload = {
  ok: boolean
  unreadCount: number
  items: TopbarNotification[]
}

export type TopbarDeadline = {
  id: string
  title: string
  dueDate: string
  priority: TopbarPriority
  status: 'open' | 'completed' | 'overdue'
  caseId: string | null
  caseTitle: string | null
  clientName: string | null
  href: string
}

export type TopbarDeadlinesPayload = {
  ok: boolean
  summary: {
    today: number
    tomorrow: number
    nextSevenDays: number
    urgent: number
    overdue: number
  }
  deadlines: TopbarDeadline[]
}

export type TopbarRecentItem = {
  id: string
  type: 'case' | 'client' | 'document' | 'matter'
  title: string
  subtitle: string | null
  href: string
  lastAccessedAt: string | null
}

export type TopbarRecentPayload = {
  ok: boolean
  items: TopbarRecentItem[]
}

export type TimeTrackingActivityType =
  | 'call'
  | 'drafting'
  | 'research'
  | 'hearing'
  | 'meeting'
  | 'email'
  | 'filing'
  | 'other'

export type TimeTrackingTimer = {
  id: string
  caseId: string | null
  clientId: string | null
  activityType: TimeTrackingActivityType
  description: string | null
  startedAt: string
  pausedAt: string | null
  endedAt: string | null
  elapsedSeconds: number
  status: 'running' | 'paused' | 'stopped'
}

export type TimeTrackingPayload = {
  ok: boolean
  timer: TimeTrackingTimer | null
  timeEntry?: { id: string; href: string } | null
}

export type TopbarCreateContext = {
  contextType: 'global' | 'case' | 'client' | 'matter'
  contextId: string | null
}

export type TopbarCreateAction = {
  id: string
  label: string
  description: string
  icon: string
  href: string
  requiresPermission: string | null
}
