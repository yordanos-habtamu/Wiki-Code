// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  devtools: { enabled: true },
  
  modules: [
    '@nuxtjs/tailwindcss'
  ],

  // Component auto-import configuration
  components: {
    dirs: [
      {
        path: '~/components',
        pathPrefix: false,
      },
      {
        path: '~/components/ui',
        pathPrefix: false,
      },
      {
        path: '~/components/dashboard',
        pathPrefix: false,
      },
      {
        path: '~/components/topology',
        pathPrefix: false,
      },
    ],
  },

  // Dev server proxy configuration
  // Proxy API requests to Python backend running on port 3000
  routeRules: {
    '/api/**': {
      proxy: 'http://localhost:3000/api/**'
    }
  },
  
  app: {
    head: {
      title: 'WikiHub Dashboard',
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'description', content: 'WikiHub Code Intelligence Dashboard' }
      ]
    }
  },
  
  runtimeConfig: {
    public: {
      apiBaseUrl: process.env.NUXT_PUBLIC_API_BASE_URL || 'http://localhost:3000'
    }
  },
  
  compatibilityDate: '2024-05-21'
})
