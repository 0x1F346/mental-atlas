// The only way the web app talks to the API. Types come from the generated schema.
import createClient, { type Middleware } from 'openapi-fetch'

import type { components, paths } from './generated/schema'

export type Schemas = components['schemas']
export type Me = Schemas['Me']
export type Source = Schemas['SourceOut']
export type Transcript = Schemas['TranscriptOut']
export type Speaker = Schemas['SpeakerOut']
export type Segment = Schemas['SegmentOut']

let csrfToken: string | null = null

export function setCsrfToken(token: string | null) {
  csrfToken = token
}

const csrf: Middleware = {
  onRequest({ request }) {
    if (csrfToken && !['GET', 'HEAD'].includes(request.method)) {
      request.headers.set('x-csrf-token', csrfToken)
    }
    return request
  },
}

export const api = createClient<paths>({
  baseUrl: window.location.origin,
  credentials: 'same-origin',
  fetch: (request) => globalThis.fetch(request),
})
api.use(csrf)

export class ApiFailure extends Error {
  readonly code: string
  readonly sourceId: string | null

  constructor(code: string, message: string, sourceId: string | null = null) {
    super(message)
    this.code = code
    this.sourceId = sourceId
  }
}

/** Unwrap an openapi-fetch result, turning the API's error shape into an exception. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.response.ok) return result.data as T
  const body = (result.error as Partial<Schemas['ErrorResponse']> | undefined)?.error
  throw new ApiFailure(
    body?.code ?? 'request_failed',
    body?.message ?? 'The request failed.',
    body?.source_id ?? null,
  )
}
