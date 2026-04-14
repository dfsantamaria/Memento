from rdflib import URIRef, Literal, RDF, RDFS, OWL, Graph, Namespace, BNode 
from rdflib import ConjunctiveGraph
from memento import MementoSM, DYNDIFF, copy_bnode_closure
from changes_s1_converted import changes_s1
from pathlib import Path

MEMENTO = Namespace("http://www.dmi.unict.memento/ontology#")
PROV = Namespace("http://www.w3.org/ns/prov#")

from rdflib import URIRef, RDF, RDFS, OWL, Graph

def collect_uris_from_bnode_closure(src_g, node):
    uris = set()
    stack = [node]
    seen = set()

    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)

        for (_, _, o) in src_g.triples((n, None, None)):
            if isinstance(o, URIRef):
                uris.add(o)
            elif isinstance(o, BNode):
                stack.append(o)

    return uris

def copy_full_expression(src_g, dst_g, node):
    stack = [node]
    seen = set()

    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)

        if (n, RDF.type, OWL.Restriction) in src_g:
            dst_g.add((n, RDF.type, OWL.Restriction))

        if (n, OWL.intersectionOf, None) in src_g:
            dst_g.add((n, RDF.type, OWL.Class))

        for (s, p, o) in src_g.triples((n, None, None)):
            dst_g.add((s, p, o))

            if p in (OWL.intersectionOf, RDF.first, RDF.rest):
                if isinstance(o, BNode):
                    stack.append(o)

            if isinstance(o, BNode):
                stack.append(o)

        for (s, p, o) in src_g.triples((None, None, n)):
            dst_g.add((s, p, o))

            if isinstance(s, BNode):
                stack.append(s)

def export_diff_as_rdf(m, ontology_name, added, removed, out_path, copy_labels=True):

    g = Graph()
    g.bind("memento", MEMENTO)
    g.bind("owl", OWL)
    g.bind("rdfs", RDFS)
    g.bind("prov", PROV)

    ocg = m.store.get_context(m._ocg_iri(ontology_name))
    meta = m.store.get_context(m.meta_graph_iri)

    g_s1 = m.get_ontology_state(ontology_name, "s1")
    g_s2 = m.get_ontology_state(ontology_name, "s2")

    TO_COPY_TYPES = {
        OWL.Class,
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
        OWL.NamedIndividual,
        OWL.Restriction
    }

    SYSTEM_PREDICATES = {
        MEMENTO.hasOntologyStateChange,
        MEMENTO.hasOntologyState,
        MEMENTO.hasPreviousState,
        OWL.annotatedSource,
        OWL.annotatedProperty,
        OWL.annotatedTarget,
        OWL.imports,
    }

    ANNOTATION_PREDICATES = {
        RDFS.label,
        RDFS.comment,
        OWL.versionInfo,
    }

    def is_removed_entity(ent):
        return any(s == ent for ((s, _, _), _) in removed if isinstance(s, URIRef))

    def get_source_graph(ent):
        return g_s1 if is_removed_entity(ent) else g_s2

    def diff_entities():
        ents = set()
        for ((s, _, _), _) in added + removed:
            if isinstance(s, URIRef):
                ents.add(s)
        return ents

    def changes_for_entity(ent):
        out = set()
        for ((s, _, _), ch) in added + removed:
            if s == ent and ch is not None:
                out.add(ch)
        return out

    def copy_entity_description(ent, src):
        """
        Copies the full OWL description of the changed entity from the proper state.
        Support URIs are NOT promoted to top-level classes.
        """
        support_uris = set()

        for p, o in src.predicate_objects(ent):

            if p in SYSTEM_PREDICATES:
                continue

            if p in ANNOTATION_PREDICATES and not copy_labels:
                continue

            if p == RDF.type:
                g.add((ent, p, o))
                continue

            g.add((ent, p, o))

            if isinstance(o, BNode):
                copy_full_expression(src, g, o)
                support_uris |= collect_uris_from_bnode_closure(src, o)

            elif isinstance(o, URIRef):
                support_uris.add(o)

        if copy_labels:
            for u in support_uris:
                if u == ent:
                    continue
                for src2 in (g_s1, g_s2):
                    for lab in src2.objects(u, RDFS.label):
                        g.add((u, RDFS.label, lab))

    def reify_entity_axioms(ent, src, ch):
        for p, o in src.predicate_objects(ent):

            if p in SYSTEM_PREDICATES:
                continue

            if p in ANNOTATION_PREDICATES:
                continue

            if p == RDF.type and o not in TO_COPY_TYPES:
                continue

            ax = BNode()
            g.add((ax, RDF.type, OWL.Axiom))
            g.add((ax, OWL.annotatedSource, ent))
            g.add((ax, OWL.annotatedProperty, p))
            g.add((ax, OWL.annotatedTarget, o))
            g.add((ax, MEMENTO.hasOntologyStateChange, ch))

    all_diff_entities = diff_entities()
    used_changes = set()

    for ent in all_diff_entities:
        src = get_source_graph(ent)
        copy_entity_description(ent, src)

        for ch in changes_for_entity(ent):
            g.add((ent, MEMENTO.hasOntologyStateChange, ch))
            used_changes.add(ch)

    for ent in all_diff_entities:
        src = get_source_graph(ent)
        for ch in changes_for_entity(ent):
            reify_entity_axioms(ent, src, ch)

    for ch in used_changes:
        for t in ocg.triples((ch, None, None)):
            g.add(t)

        for st in ocg.objects(ch, MEMENTO.hasOntologyState):
            for t in meta.triples((st, None, None)):
                g.add(t)

            for ver in meta.objects(st, MEMENTO.hasOntologyStateVersion):
                for t in meta.triples((ver, None, None)):
                    g.add(t)

            for ag in meta.objects(st, PROV.wasGeneratedBy):
                for t in meta.triples((ag, None, None)):
                    g.add(t)

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

        # NON toccare i BNode
        if isinstance(s, URIRef):
            s = URIRef(str(s))

        if isinstance(p, URIRef):
            p = URIRef(str(p))

        if isinstance(o, URIRef):
            o = URIRef(str(o))
        elif isinstance(o, Literal):
            o = Literal(str(o), lang=o.language, datatype=o.datatype)
        elif isinstance(o, str):
            pass

        out.append(((s, p, o), op))
    return out

changes_s1 = normalize_changes(changes_s1)

TARGET_CLASS = URIRef(
    "https://bioportal.bioontology.org/ontologies/SCTO#SCTO_7389001"
)

def filter_changes_for_class(changes, target):
    filtered = []
    seen = set()
    frontier = set()

    for item in changes:
        (s, p, o), op = item
        if s == target:
            filtered.append(item)
            seen.add(item)
            if isinstance(o, BNode):
                frontier.add(o)

    changed = True
    while changed:
        changed = False
        for item in changes:
            if item in seen:
                continue

            (s, p, o), op = item

            if isinstance(s, BNode) and s in frontier:
                filtered.append(item)
                seen.add(item)
                changed = True

                if isinstance(o, BNode) and o not in frontier:
                    frontier.add(o)

    return filtered

changes_s1_one_class = filter_changes_for_class(
    changes_s1,
    TARGET_CLASS
)

print("\n===s1 CREATION===")
s1 = m.create_ontology_state(
    ontology_name=ONTO,
    changes=changes_s1_one_class,
    previous_state="s0",
    state_name="s1",
    author="Shaker_El-Sappagh",
    version="2.0.0",      
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

print("\n===s2 CREATION===")
s2 = m.create_ontology_state(
    ontology_name=ONTO,
    changes=changes_s2,
    previous_state="s1",
    state_name="s2",
    author="Shaker_El-Sappagh",
    version="2.0.0-remove-one",
    bulk=False
)

export_full_state(m, ONTO, "s2", OUT_S2)

g = m.get_ontology_state(ONTO, "s2")

# =======================
# 4) S3 — REVERT
# =======================

print("\n===s3 CREATION===")
s3 = m.revert_ontology(
    ONTO,
    target_state="s1",
    new_state_name="s3",
    author="Shaker_El-Sappagh",
    version="2.0.0-revert"
)

export_full_state(m, ONTO, "s3", OUT_S3)

g = m.get_ontology_state(ONTO, "s3")

# =======================
# 5) DIFF 
# =======================

print("\n=== DIFF s1 → s2 ===")
added, removed = m.get_ontology_state_diff(ONTO, "s1", "s2")

OUT_DIFF = BASE_OUT / "SCTO_diff_s1_s2.ttl"
export_diff_as_rdf(m, ONTO, added, removed, OUT_DIFF)
