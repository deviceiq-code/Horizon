import { catalog } from '@/modules/catalogs'

/** A catalog of Administration (/admin/catalogs/service-providers). */
const serviceProviders = catalog(
  'service-providers',
  'service-providers',
  'mdi-account-hard-hat-outline',
  'serviceProviders',
  () => import('./ServiceProvidersTab.vue'),
)

export default serviceProviders
