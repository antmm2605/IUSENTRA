export type ApiMethod = 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE'

export type ApiWarning = {
  code?: string
  message: string
}

export type ApiValidationErrors = Record<string, string>

export type ApiErrorPayload = {
  ok?: false
  message?: string
  errore?: string
  errors?: ApiValidationErrors
  warnings?: ApiWarning[]
  status?: number
  code?: string
}

export type ApiRequestOptions = {
  /** false for periodic background checks; text for an explicit operation. */
  activity?: string | false
  signal?: AbortSignal
  headers?: HeadersInit
  retry?: boolean
}

export type ApiMutationOptions = ApiRequestOptions & {
  method?: Exclude<ApiMethod, 'GET'>
}
