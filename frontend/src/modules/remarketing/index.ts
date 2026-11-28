/**
 * Remarketing (an app of the suite): the sale of used assets — offers, buyers, sales and
 * sales channels. A skeleton for now: each module is a page saying what it will hold
 * (`components/UnderConstruction.vue`) while the business rules are defined; the backend app
 * is `remarketing/` (no models yet). The inventory (formerly this app) is Asset Management.
 */
import type { AppModule } from '@/modules'

function page(name: string, path: string, key: string, icon: string): AppModule {
  return {
    name,
    icon,
    titleKey: `remarketing.${key}.title`,
    app: 'remarketing',
    routes: [
      {
        path,
        name,
        component: () => import('@/components/UnderConstruction.vue'),
        props: { textKey: `remarketing.${key}`, icon },
      },
    ],
  }
}

export default [
  page('remarketing-offers', 'offers', 'offers', 'mdi-bullhorn-outline'),
  page('remarketing-sales', 'sales', 'sales', 'mdi-cart-outline'),
  page('remarketing-buyers', 'buyers', 'buyers', 'mdi-account-cash-outline'),
  page('remarketing-channels', 'sales-channels', 'channels', 'mdi-web'),
]
