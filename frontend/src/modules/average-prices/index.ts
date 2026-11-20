import type { AppModule } from '@/modules'

const averagePrices: AppModule = {
  name: 'average-prices',
  icon: 'mdi-chart-timeline-variant',
  titleKey: 'averagePrices.title',
  app: 'pricing',
  routes: [
    {
      path: 'average-prices',
      name: 'average-prices',
      component: () => import('./AveragePricesView.vue'),
    },
  ],
}

export default averagePrices
