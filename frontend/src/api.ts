/** Cliente HTTP do backend Django: envia o cookie de sessão e o token CSRF. */

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function lerCookie(nome: string): string | null {
  const m = document.cookie.match(new RegExp('(^|;\\s*)' + nome + '=([^;]*)'))
  return m && m[2] ? decodeURIComponent(m[2]) : null
}

export async function api<T = unknown>(caminho: string, opcoes: RequestInit = {}): Promise<T> {
  const metodo = (opcoes.method ?? 'GET').toUpperCase()
  const headers = new Headers(opcoes.headers)
  if (opcoes.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }
  if (!['GET', 'HEAD', 'OPTIONS'].includes(metodo)) {
    const token = lerCookie('csrftoken')
    if (token) headers.set('X-CSRFToken', token)
  }

  const resp = await fetch(`/api${caminho}`, {
    ...opcoes,
    method: metodo,
    headers,
    credentials: 'same-origin',
  })

  if (!resp.ok) {
    let mensagem = resp.statusText
    try {
      const dados = await resp.json()
      mensagem = dados.detail ?? mensagem
    } catch {
      /* resposta sem corpo JSON */
    }
    throw new ApiError(resp.status, mensagem)
  }
  if (resp.status === 204) return undefined as T
  return (await resp.json()) as T
}
