import type { Messages } from './en'

const ptBR: Messages = {
  app: {
    name: 'Sistema Horizon',
    description: 'Precificação de residuais de leasing operacional',
  },
  common: {
    logout: 'Sair',
  },
  language: {
    select: 'Selecionar idioma',
  },
  login: {
    username: 'Usuário',
    password: 'Senha',
    submit: 'Entrar',
    invalidCredentials: 'Usuário ou senha inválidos.',
  },
  menu: {
    open: 'Abrir menu',
    home: 'Início',
    settings: 'Configurações',
  },
  home: {
    welcome: 'Bem-vindo, {name}',
    text: 'O ambiente está funcionando. Aqui entrarão as telas de ativos, curvas de residual e simulações de precificação.',
  },
  settings: {
    title: 'Configurações',
    subtitle: 'Suas preferências ficam salvas na sua conta e valem em qualquer dispositivo.',
    language: 'Idioma',
    languageDescription: 'Idioma da interface e das mensagens do sistema.',
    appearance: 'Aparência',
    theme: 'Tema',
    themeDescription: 'Cores claras, escuras ou iguais às do seu sistema operacional.',
    themes: {
      light: 'Claro',
      dark: 'Escuro',
      system: 'Sistema',
    },
    saved: 'Preferências salvas.',
    saveError: 'Não foi possível salvar as preferências. Tente novamente.',
  },
}

export default ptBR
