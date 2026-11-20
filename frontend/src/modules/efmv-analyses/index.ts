import { RouterView } from 'vue-router'
import type { AppModule } from '@/modules'

const efmvAnalyses: AppModule = {
  name: 'efmv-analyses',
  icon: 'mdi-file-chart-outline',
  titleKey: 'efmv.title',
  app: 'pricing',
  routes: [
    {
      // The menu links here; the list, a new analysis and an analysis are its pages
      path: 'efmv-analyses',
      name: 'efmv-analyses',
      component: RouterView,
      redirect: { name: 'efmv-analyses-list' },
      children: [
        {
          path: '',
          name: 'efmv-analyses-list',
          component: () => import('./EfmvAnalysesView.vue'),
        },
        {
          path: 'new',
          name: 'efmv-analysis-new',
          meta: { titleKey: 'efmv.newTitle' },
          component: () => import('./EfmvAnalysisView.vue'),
        },
        {
          path: ':id(\\d+)',
          name: 'efmv-analysis',
          meta: { titleKey: 'efmv.analysis' },
          component: () => import('./EfmvAnalysisView.vue'),
          props: (route) => ({ id: Number(route.params.id) }),
        },
      ],
    },
  ],
}

export default efmvAnalyses
