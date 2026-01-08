from rdflib import URIRef, Literal, RDF, RDFS, OWL
from rdflib import ConjunctiveGraph
from memento import MementoSM, DYNDIFF

# =======================
# CONFIGURAZIONE
# =======================
ONTO = "SCTO"
SCTO_PATH = r"C:\Users\laura\Downloads\SCTO1.0.ttl"

OUT_S1 = r"C:\Users\laura\Downloads\SCTO_state1_FULL_safe.ttl"
OUT_S2 = r"C:\Users\laura\Downloads\SCTO_state2_FULL_safe.ttl"
OUT_S3 = r"C:\Users\laura\Downloads\SCTO_state3_FULL_safe.ttl"
OUT_S4 = r"C:\Users\laura\Downloads\SCTO_state4_FULL_safe.ttl"


# =======================
# FUNZIONE EXPORT
# =======================
def export_full_state(m, ontology_name, state_name, out_path):
    cg = ConjunctiveGraph()

    # Solo lo STATE graph!
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
s1 = m.create_ontology(ONTO, SCTO_PATH, "s1", "Laura", version="1.0")

export_full_state(m, ONTO, "s1", OUT_S1)


# =======================
# 2) CREAZIONE s2 con cambiamenti (addC, addP, addI)
# =======================
print("\n=== CREAZIONE s2 (modifiche) ===")

changes_s2 = [
    # ADD CLASS
    ((URIRef("http://example.org/NewClass"), RDF.type, OWL.Class), DYNDIFF.addC),

    # ADD PROPERTY
    ((URIRef("http://example.org/newProperty"), RDF.type, OWL.ObjectProperty), DYNDIFF.addP),

    # ADD LABEL to an existing SCTO class
    (
        (URIRef("https://bioportal.bioontology.org/ontologies/SCTO#Patient"),
         RDFS.label,
         Literal("Patient NEW label", lang="en")),
        DYNDIFF.addI
    ),

    # DEL LABEL esistente (TEST DELCHANGEACTION)
    (
        (URIRef("http://purl.obolibrary.org/obo/OGMS_0000085"),
         RDF.type,
         OWL.Class),
        DYNDIFF.delC
    )
]

s2 = m.create_ontology_state(
    ONTO, changes_s2, "s2", "Laura", version="2.0", prev_state_name="s1"
)

export_full_state(m, ONTO, "s2", OUT_S2)


# =======================
# 3) CREAZIONE s3 con REVERT (revert a s1)
# =======================
print("\n=== REVERT: CREAZIONE s3 (revert a s1) ===")

s3 = m.revert_ontology(ONTO, "s1", "s3", "Laura")

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
    ONTO, changes_s4, "s4", "Laura", version="4.0", prev_state_name="s2"
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

print("\n=== TEST COMPLETO FINITO ===")
