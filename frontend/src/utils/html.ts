/** Text put into hand-written HTML (printed documents): &, <, >, " and ' escaped. */
export const escapeHtml = (text: string) => text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`)
