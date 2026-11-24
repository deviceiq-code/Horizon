/**
 * Services, Partners and Alliances (an app of the suite): the services and software Horizon
 * offers, partners, incentive programs, discounts and fees. A skeleton for now: each module is
 * a page saying what it will hold (`UnderConstruction.vue`) while the business rules are
 * defined; the backend app is `partners/` (no models yet).
 */
import type { AppModule } from '@/modules'

function page(name: string, path: string, key: string, icon: string): AppModule {
  return {
    name,
    icon,
    titleKey: `partners.${key}.title`,
    app: 'partners',
    routes: [
      {
        path,
        name,
        component: () => import('./UnderConstruction.vue'),
        props: { page: key, icon },
      },
    ],
  }
}

export default [
  page('partners-services', 'services', 'services', 'mdi-toolbox-outline'),
  page('partners-partners', 'partners', 'partners', 'mdi-handshake-outline'),
  page('partners-incentives', 'incentive-programs', 'incentives', 'mdi-gift-outline'),
  page('partners-discounts', 'discounts-and-fees', 'discounts', 'mdi-percent-outline'),
]
