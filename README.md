# MEMENTO — Meta-Annotated Change Graph Based Management of Evolving Ontologies

MEMENTO (Meta-Annotated Change Graph Based Management of Evolving Ontologies) is a framework for managing evolving ontologies by tracking changes at the RDF statement level. It integrates DynDiffOnto, PROV-O, and RDF/OWL annotations to represent ontology states, versions, changes, and provenance in a unified knowledge graph. MEMENTO supports ontology version tracking, state retrieval, change/delta computation, and rollback operations, enabling transparent and queryable management of ontology evolution.

MEMENTO first appeared to the proceedings of 8th International Knowledge Graph and Semantic Web Conference (KGSWC 2026).

Please cite the following paper:
"Astuto, C., Biondi, S., Brisindi, L., De Felice, C., Longo, C. F., Mangano, M. G., Nicolosi Asmundo, M., Santamaria, D. F. MEMENTO - Meta-Annotated Change Graph Based Management of Evolving Ontologies. Proceedings of the 8th International Knowledge Graph and Semantic Web Conference (KGSWC)."

## Main Features

MEMENTO currently supports:

* Tracking ontology states over time
* Recording individual RDF-level changes
* Associating changes with ontology states
* Recording change authors and timestamps
* Representing ontology state versions using Semantic Versioning 2.0
* Retrieving specific ontology states
* Computing the difference between two ontology states
* Reverting an ontology to a previous state
* Querying the resulting RDF representation using standard SPARQL
* Maintaining provenance information through PROV-O

The current implementation represents two general categories of changes:

* `AddChangeAction`
* `DelChangeAction`

## These encompass the addition and deletion operations represented in DynDiffOnto.

## Architecture

MEMENTO is organized around two main components:

### MEMENTO Software Module (MEMENTO-SM)

The software module acts as middleware for reading and writing ontology changes, retrieving ontology states, and querying the stored data.

The implementation uses:

* **RDFLib** for RDF triple manipulation
* **OpenLink Virtuoso** for persistent RDF storage and querying

### MEMENTO Ontology Module (MEMENTO-OM)

MEMENTO-OM integrates:

* **DynDiffOnto**, for representing ontology changes
* **PROV-O**, for provenance
* **MEMENTO-O**, the ontology

The resulting knowledge base contains an **Ontology Change Graph (OCG)** and a collection of **Ontology State Graphs**. The OCG records the accumulated changes, while each state graph represents the ontology at a particular point in its evolution. It can be visually presented as


```text
                    MEMENTO Knowledge Base
                             |
                    MEMENTO Ontology Module
                       /        |        \
                      /         |         \
              DynDiffOnto     PROV-O    MEMENTO-O
                    \           |          /
                     \          |         /
                      +------------------+
                      |                  |
              Ontology Change       Ontology State
                   Graphs              Graphs
```

---

## MEMENTO Ontology

The MEMENTO ontology introduces the following main concepts and properties.

### Main classes

* `OntologyState`
* `OntologyStateVersion`

`OntologyState` represents the ontology at a specific point in time and is connected to the provenance information associated with its creation.

`OntologyStateVersion` represents the version of an ontology state using Semantic Versioning 2.0.

### Main properties

* `hasOntologyState`
* `hasOntologyStateChange`
* `hasOntologyStateVersion`
* `hasPreviousState`
* `hasNextState`
