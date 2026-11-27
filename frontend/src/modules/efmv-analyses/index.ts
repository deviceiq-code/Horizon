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
          // A wizard sets the premises; then the analysis opens with a first scenario
          component: () => import('./EfmvWizardView.vue'),
        },
        {
          path: ':id(\\d+)',
          name: 'efmv-analysis',
          meta: { titleKey: 'efmv.analysis' },
          component: () => import('./EfmvAnalysisView.vue'),
          // ?scenario=<id>: opens on that scenario's tab (e.g. clicked on the list)
          props: (route) => ({
            id: Number(route.params.id),
            scenario: route.query.scenario ? Number(route.query.scenario) : undefined,
          }),
        },
      ],
    },
  ],
}

export default efmvAnalyses
