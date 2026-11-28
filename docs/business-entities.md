# Business Entities (Entidades)

One register for every company or person Horizon deals with. What they all have in common
(identification, contact, address) lives in the **entity**; what each kind of relationship needs
lives in a **role** of it. Dell may be a supplier, and later a customer and a service provider
too: one entity, three roles.

## Decisions

- **Name**: "Business Entities" (en), "Entidades" (pt-br, es). Administration › Catalogs, one
  page replacing Customers and Service Providers (their former addresses are gone).
- **Entity** (`entities.BusinessEntity`): legal name, trade name, tax ID (CPF/CNPJ in Brazil,
  validated; unique per country), country, contact name, e-mail, phone, address, active, notes,
  keywords, and its **head office** (`parent`, optional).
- **Head office and groups**: when created (or later), an entity may point to its head office
  among the entities already registered. Groups are not registered: the tree under an entity
  without a head office is its group. No cycles: an entity's head office cannot be itself nor
  one of its branches, at any depth (`entities/hierarchy.py`, pure). A head office with
  branches cannot be deleted. For a Brazilian CNPJ, the form suggests the entity with the
  same root (the first 8 characters; `/0001` preferred) — only a suggestion.
- **Roles** (one table each, 1:1 with the entity; an entity has any of them):

  | Role | en | pt-br | es | Own data |
  |---|---|---|---|---|
  | `customer` | Customer | Cliente | Cliente | account managers; contract types |
  | `supplier` | Supplier | Fornecedor | Proveedor | supplies products and/or services |
  | `service_provider` | Service Provider | Service Provider | Service Provider | services |
  | `buyer` | Buyer | Comprador | Comprador | — |

  A customer's **contract types** ("Modalidades"; optional — a prospect has none): Renter /
  Locatário / Locatario, Lessee / Arrendatário / Arrendatario, Bailee (Free Loan) / Comodatário
  / Comodatario, Service Customer / Tomador de Serviços / Cliente de Servicios. Selling goods is
  not one: buyers are a role. (A Lessee role existed at first; it became these.)
- `customers.Customer` and `service_providers.ServiceProvider` stay as the tables of their
  roles — same ids, so every foreign key to them (eFMV analyses, appointments, disposals,
  transfers, warehouses) is untouched; their common fields moved to the entity.
- **Active per role**, besides the entity's: an entity may stop being a customer and still be
  a service provider. A role that records point to cannot be removed (409): deactivate it.
  Pickers offer only entities active in the role (and active themselves).
- **Migration**: customers and service providers with the same country and tax ID became one
  entity; values that differed were listed for review (the customer's kept).
- **Third-party sales** (disposals): the buyer is an entity with the Buyer role; the existing
  sales gave the role to their buyers.
- **Manufacturers** stay a catalog of brands; a brand may point to the business entity behind
  it (optional; chosen in its form; the entity then cannot be deleted).

## Pages

Administration › Catalogs › Business Entities: tabs — one per role (Customers, Suppliers,
Service Providers, Buyers), then All last (every entity, its roles as chips, head office /
group; opened by default) with that role's columns and its active flag; an entity with several roles shows in
each of their tabs; New in a role's tab starts with that role. The form: the entity (identity,
head office, address, contact, notes, keywords) and its roles — each one turned on opens its
own tab.

## Phases

1. Backend: entity, roles, migration, API (`/api/business-entities/`), the former endpoints
   read-only for the pickers, search.
2. Frontend: the page with tabs and the form; the pickers follow.
3. Supplier and Buyer roles, customers' contract types; third-party sales' buyers.
4. Manufacturers linked to business entities.
