export const endpoints = {
  bootstrap: "/api/v1/ui/bootstrap",
  dashboard: "/api/v1/ui/dashboard",
  fascicolo: (id: string) => `/api/v1/ui/fascicoli/${encodeURIComponent(id)}`,
  lexChat: "/api/v1/ui/lex/chat",
};
