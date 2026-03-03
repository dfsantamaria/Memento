from rdflib import URIRef, Literal, RDF, RDFS, OWL, Graph, Namespace, BNode
from rdflib import ConjunctiveGraph
from memento import MementoSM, DYNDIFF
from changes_s1_converted import changes_s1
from pathlib import Path

MEMENTO = Namespace("http://www.dmi.unict.memento/ontology#")
PROV = Namespace("http://www.w3.org/ns/prov#")

from rdflib import URIRef, RDF, RDFS, OWL, Graph

def export_diff_as_rdf(m, ontology_name, added, removed, out_path, copy_labels=True):

    g = Graph()
    g.bind("memento", MEMENTO)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)
    g.bind("prov", PROV)

    ocg = m.store.get_context(m._ocg_iri(ontology_name))

    target_state = "s2"
    target_state_iri = m._state_iri(ontology_name, target_state)
    g_s2 = m.get_ontology_state(ontology_name, target_state)

    changes_to_export = set()
    touched_entities = set()

    def collect(delta):
        for (s, p, o), _ in delta:
            for ax in ocg.subjects(OWL.annotatedSource, s):
                if (ax, OWL.annotatedProperty, p) not in ocg:
                    continue
                if (ax, OWL.annotatedTarget, o) not in ocg:
                    continue
                for ch in ocg.objects(ax, MEMENTO.hasOntologyStateChange):
                    if (ch, MEMENTO.hasOntologyState, target_state_iri) in ocg:
                        changes_to_export.add(ch)

    collect(added)
    collect(removed)

    for ch in changes_to_export:
        for ax in ocg.subjects(MEMENTO.hasOntologyStateChange, ch):

            ap = next(ocg.objects(ax, OWL.annotatedProperty), None)

            if ap in (RDFS.label, RDFS.comment):
                continue

            if ap == RDFS.subClassOf:
                continue

            s_ent = next(ocg.objects(ax, OWL.annotatedSource), None)
            o_tgt = next(ocg.objects(ax, OWL.annotatedTarget), None)

            if s_ent is None or o_tgt is None:
                continue

            touched_entities.add(s_ent)

            g.add((ax, RDF.type, OWL.Axiom))
            g.add((ax, OWL.annotatedSource, s_ent))
            g.add((ax, OWL.annotatedProperty, ap))
            g.add((ax, OWL.annotatedTarget, o_tgt))

            g.add((ax, MEMENTO.hasOntologyStateChange, ch))
            g.add((s_ent, MEMENTO.hasOntologyStateChange, ch))

    TO_COPY_TYPES = {
        OWL.Class,
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
        OWL.NamedIndividual
    }

    for ent in touched_entities:
        for t in g_s2.objects(ent, RDF.type):
            if t in TO_COPY_TYPES:
                g.add((ent, RDF.type, t))

        if copy_labels:
            for lab in g_s2.objects(ent, RDFS.label):
                g.add((ent, RDFS.label, lab))

    for ch in changes_to_export:
        for t in ocg.objects(ch, RDF.type):
            g.add((ch, RDF.type, t))

    g.serialize(out_path, format="turtle")

# =======================
# CONFIGURATION
# =======================

ONTO = "SCTO"

BASE_DIR = Path(__file__).resolve().parent
SCTO_0_PATH = BASE_DIR / "SCTO_1.0.ttl"

BASE_OUT = Path("output")

BASE_OUT.mkdir(exist_ok=True)

OUT_S0 = BASE_OUT / "SCTO_state0.ttl"
OUT_S1 = BASE_OUT / "SCTO_state1.ttl"
OUT_S2 = BASE_OUT / "SCTO_state2_remove.ttl"
OUT_S3 = BASE_OUT / "SCTO_state3_revert.ttl"
OUT_DIFF = BASE_OUT / "SCTO_delta_s0_s1.ttl"

# =======================
# EXPORT FUNCTION
# =======================

def export_full_state(m, ontology_name, state_name, out_path):
    cg = ConjunctiveGraph()
    ctx = m.store.get_context(m._state_graph_iri(ontology_name, state_name))
    for t in ctx:
        cg.add(t)
    cg.serialize(out_path, format="turtle")

# =======================
# INIT
# =======================

m = MementoSM()

# =======================
# 1) S1 — SCTO 1.0
# =======================

print("\n=== s0 CREATION ===")

s0 = m.create_ontology(
    ONTO,
    SCTO_0_PATH,
    "s0",
    "Shaker_El-Sappagh",
    version="1.0.0"
)

export_full_state(m, ONTO, "s0", OUT_S0)

# =======================
# 2) S1 — SCTO 2.0 
# =======================

def normalize_changes(changes):
    out = []
    for (s, p, o), op in changes:
        s = URIRef(str(s))
        p = URIRef(str(p))
        if isinstance(o, URIRef):
            o = URIRef(str(o))
        elif isinstance(o, Literal):
            o = Literal(str(o), lang=o.language, datatype=o.datatype)
        elif isinstance(o, str):
            o = Literal(o)
        out.append(((s, p, o), op))
    return out

changes_s1 = normalize_changes(changes_s1)

TARGET_CLASS = URIRef(
    "https://bioportal.bioontology.org/ontologies/SCTO#SCTO_7389001"
)

def filter_changes_for_class(changes, target):
    filtered = []
    for (s, p, o), op in changes:
        if s == target:
            filtered.append(((s, p, o), op))
    return filtered

changes_s1_one_class = filter_changes_for_class(
    changes_s1,
    TARGET_CLASS
)

s1 = m.create_ontology_state(
    ontology_name=ONTO,
    changes=changes_s1_one_class,
    state_name="s1",
    author="Shaker_El-Sappagh",
    version="2.0.0",      
    prev_state_name="s0",
    bulk=False
)

export_full_state(m, ONTO, "s1", OUT_S1)

# =======================
# 3) S2 — REMOVE
# =======================

def invert_change_type(ch_type):
    local = str(ch_type)
    if local.endswith("addC"): return DYNDIFF.delC
    if local.endswith("addP"): return DYNDIFF.delP
    if local.endswith("addI"): return DYNDIFF.delI
    if local.endswith("delC"): return DYNDIFF.addC
    if local.endswith("delP"): return DYNDIFF.addP
    if local.endswith("delI"): return DYNDIFF.addI
    return ch_type

changes_s2 = [(t, invert_change_type(tp)) for (t, tp) in changes_s1_one_class]

s2 = m.create_ontology_state(
    ontology_name=ONTO,
    changes=changes_s2,
    state_name="s2",
    author="Shaker_El-Sappagh",
    version="2.0.0-remove-one",
    prev_state_name="s1",
    bulk=False
)

export_full_state(m, ONTO, "s2", OUT_S2)

print("\n=== CHECK subclassOf time frame ===")

# =======================
# 4) S3 — REVERT
# =======================

s3 = m.revert_ontology(
    ONTO,
    target_state="s1",
    new_state_name="s3",
    author="Shaker_El-Sappagh",
    version="2.0.0-revert"
)

export_full_state(m, ONTO, "s3", OUT_S3)

# =======================
# 5) DIFF 
# =======================

print("\n=== DIFF s1 → s2 ===")
added, removed = m.get_ontology_state_diff(ONTO, "s1", "s2")
OUT_DIFF = BASE_OUT / "SCTO_diff_s1_s2.ttl"
export_diff_as_rdf(m, ONTO, added, removed, OUT_DIFF)
