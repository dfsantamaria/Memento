from rdflib import URIRef, Literal, RDF, RDFS, OWL
from rdflib import ConjunctiveGraph
from memento import MementoSM, DYNDIFF
from memento import MEMENTO 

# =======================
# CONFIGURAZIONE
# =======================
ONTO = "TEST"
SCTO_PATH = r"C:\Users\laura\Downloads\testing-ontology.ttl"

OUT_S1 = r"C:\Users\laura\Downloads\testing_state1_FULL_safe.ttl"
OUT_S2 = r"C:\Users\laura\Downloads\testing_state2_FULL_safe.ttl"
OUT_S3 = r"C:\Users\laura\Downloads\testing_state3_FULL_safe.ttl"
OUT_S4 = r"C:\Users\laura\Downloads\testing_state4_FULL_safe.ttl"


# =======================
# FUNZIONE EXPORT
# =======================
def export_full_state(m, ontology_name, state_name, out_path, use_sparql=False):
    cg = ConjunctiveGraph()

    if use_sparql:
        ctx = m.get_ontology_state(ontology_name, state_name, use_sparql=True)
    else:
        ctx = m.store.get_context(m._state_graph_iri(ontology_name, state_name))

    for t in ctx:
        cg.add(t)

    cg.serialize(out_path, format="turtle")
    print(f"[OK] Protégé-safe esportato in: {out_path}")

# =======================
# INIZIALIZZO MEMENTO-SM
# =======================
m = MementoSM()
#m = MementoSM(
    #virtuoso_query_endpoint="http://localhost:8890/sparql",
    #virtuoso_update_endpoint="http://localhost:8890/sparql",
    #base_graph_uri="http://example.org/memento"
#)

# =======================
# 1) CREAZIONE s1 (snapshot iniziale)
# =======================
print("\n=== CREAZIONE s1 ===")
s1 = m.create_ontology(ONTO, SCTO_PATH, "s1", "Laura", version="1.0.0-alpha")

export_full_state(m, ONTO, "s1", OUT_S1)


# =======================
# 2) CREAZIONE s2 con cambiamenti (addC, addP, addI)
# =======================
print("\n=== CREAZIONE s2 (modifiche) ===")

changes_s2 = [
    # ADD CLASS (tripla reale)
    ((URIRef("http://example.org/NewClass"), RDF.type, OWL.Class), DYNDIFF.addC),

    # ADD PROPERTY (tripla reale)
    ((URIRef("http://example.org/newProperty"), RDF.type, OWL.ObjectProperty), DYNDIFF.addP),

    # ADD LABEL (questa VA BENE così)
    (
        (URIRef("https://bioportal.bioontology.org/ontologies/SCTO#Patient"),
         RDFS.label,
         Literal("Patient NEW label", lang="en")),
        DYNDIFF.addI
    ),

    # REMOVE CLASS
    ((URIRef("http://www.semanticweb.org/danie/ontologies/2025/10/untitled-ontology-55#A"),
      RDF.type,
      OWL.Class),
     DYNDIFF.delC)
]

s2 = m.create_ontology_state(
    ONTO, changes_s2, "s2", "Laura", version="1.0.1-alpha", prev_state_name="s1", bulk=False
)

export_full_state(m, ONTO, "s2", OUT_S2)

print("\n=== TEST get_ontology_state: store vs sparql ===")

ctx_store = m.get_ontology_state(ONTO, "s2", use_sparql=False)
ctx_sparql = m.get_ontology_state(ONTO, "s2", use_sparql=True)

set_store = set(ctx_store)
set_sparql = set(ctx_sparql)

print("Triples (store):", len(set_store))
print("Triples (sparql):", len(set_sparql))

only_store = set_store - set_sparql
only_sparql = set_sparql - set_store

print("Solo in store:", len(only_store))
print("Solo in sparql:", len(only_sparql))

if only_store:
    print("Esempio solo store:", list(only_store)[:5])
if only_sparql:
    print("Esempio solo sparql:", list(only_sparql)[:5])

assert set_store == set_sparql, "Store e SPARQL NON coincidono"
print("Store e SPARQL coincidono perfettamente")

# =======================
# 3) CREAZIONE s3 con REVERT (revert a s1)
# =======================
print("\n=== REVERT: CREAZIONE s3 (revert a s1) ===")

s3 = m.revert_ontology(
    ONTO,
    "s1",
    "s3",
    "Laura",
    version="1.0.2-alpha"
)

export_full_state(m, ONTO, "s3", OUT_S3)

# =======================
# 4) CREAZIONE s4 con RIMOZIONE (delC, delP, delI)
# =======================
print("\n=== CREAZIONE s4 (rimozioni) ===")

changes_s4 = [
    # REMOVE the class added in s2
    ((URIRef("http://example.org/NewClass"), RDF.type, OWL.Class), DYNDIFF.delC),

    # REMOVE the property added in s2
    ((URIRef("http://example.org/newProperty"), RDF.type, OWL.ObjectProperty), DYNDIFF.delP),

    # REMOVE the new label
    (
        (URIRef("https://bioportal.bioontology.org/ontologies/SCTO#Patient"),
         RDFS.label,
         Literal("Patient NEW label", lang="en")),
        DYNDIFF.delI
    )
]

s4 = m.create_ontology_state(
    ONTO, changes_s4, "s4", "Laura", version="1.0.3-alpha", prev_state_name="s2"
)

export_full_state(m, ONTO, "s4", OUT_S4)


# =======================
# 5) DIFF TEST: s1–s2, s2–s3, s2–s4
# =======================
def print_diff(label, a, b):
    print(f"\n=== DIFF {label} ({a} → {b}) ===")
    added, removed = m.get_ontology_state_diff(ONTO, a, b)

    print("\nAggiunte:")
    for t, tp in added:
        print("  +", t, "| type:", tp)

    print("\nRimosse:")
    for t, tp in removed:
        print("  -", t, "| type:", tp)

print_diff("s1→s2", "s1", "s2")
print_diff("s2→s3", "s2", "s3")
print_diff("s2→s4", "s2", "s4")

# prende l'intero triple store (tutti i named graph)
cg = ConjunctiveGraph(store=m.store.store)

q = """
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX memento: <http://www.dmi.unict.memento/ontology#>

SELECT ?ax ?ch WHERE {
  GRAPH ?g {
    ?ax a owl:Axiom ;
        memento:hasOntologyStateChange ?ch .
    ?ch a memento:AddChangeAction .
  }
}
"""

assert (
    URIRef("http://example.org/NewClass"),
    RDF.type,
    OWL.Class
) in set_store

assert (
    URIRef("http://www.semanticweb.org/danie/ontologies/2025/10/untitled-ontology-55#A"),
    RDF.type,
    OWL.Class
) not in set_store

assert any(
    (s, MEMENTO.hasOntologyStateChange, None) in ctx_store
    for s in [
        URIRef("http://example.org/NewClass"),
        URIRef("http://example.org/newProperty")
    ]
)

ocg = m.store.get_context(m._ocg_iri(ONTO))

added, removed = m.get_ontology_state_diff(ONTO, "s1", "s2")

assert any(
    ch and (ch, RDF.type, DYNDIFF.addC) in ocg
    for _, ch in added
), "addC non trovato in s1→s2"

s2_iri = m._state_iri(ONTO, "s2")

assert any(
    (ch, RDF.type, DYNDIFF.delC) in ocg and
    (ch, MEMENTO.hasOntologyState, s2_iri) in ocg
    for ch in ocg.subjects(RDF.type, DYNDIFF.delC)
), "delC non trovato in s2"

print("Diff s1→s2 semanticamente corretto")

ctx_s1 = set(m.get_ontology_state(ONTO, "s1"))
ctx_s3 = set(m.get_ontology_state(ONTO, "s3"))

content_s1 = {
    (s,p,o) for (s,p,o) in ctx_s1
    if m.is_content_triple(s,p,o)
}

content_s3 = {
    (s,p,o) for (s,p,o) in ctx_s3
    if m.is_content_triple(s,p,o)
}

assert content_s1 == content_s3, "Revert NON semanticamente corretto"
print("Revert semanticamente corretto (s3 ≡ s1)")

assert m.get_ontology_state(ONTO, "s4"), "s4 deve esistere prima"
m.remove_ontology_state(ONTO, "s4")

try:
    list(m.get_ontology_state(ONTO, "s4"))
    assert False, "s4 non doveva esistere"
except:
    print("Stato s4 rimosso correttamente")

print("\n=== TEST COMPLETO FINITO ===")