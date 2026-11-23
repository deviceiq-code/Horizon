import { catalog } from '@/modules/catalogs'

/** A catalog of Administration (/admin/catalogs/customers; the former /admin/customers opens it). */
const customers = catalog(
  'customers',
  'customers',
  'mdi-domain',
  'customers',
  () => import('./CustomersTab.vue'),
)
customers.routes.push({ path: 'customers', redirect: { name: 'customers' } })

export default customers
