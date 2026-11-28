import { catalog } from '@/modules/catalogs'

/** Business Entities (Administration › Catalogs, /admin/catalogs/business-entities): every
 * company or person Horizon deals with and their roles — customers, lessees, suppliers,
 * service providers, buyers (docs/business-entities.md). */
const businessEntities = catalog(
  'business-entities',
  'business-entities',
  'mdi-domain',
  'businessEntities',
  () => import('./BusinessEntitiesTab.vue'),
)

export default businessEntities
