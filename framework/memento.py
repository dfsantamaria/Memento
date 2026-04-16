# ================================================================
# MEMENTO-SM
# MODULE 1 — Namespaces, Costants, Utility, IRI Factories
# ================================================================

from rdflib import (
    Graph, ConjunctiveGraph, URIRef, BNode, Literal, Namespace
)
from rdflib.namespace import RDF, RDFS, OWL, XSD
from rdflib.plugins.stores.sparqlstore import SPARQLUpdateStore
from datetime import datetime
from uuid import uuid4
import re

# ==========================
# OFFICIALS NAMESPACES
# ==========================

MEMENTO = Namespace("http://www.dmi.unict.memento/ontology#")
DYNDIFF = Namespace("http://www.list.lu/change-ontology/")
PROV = Namespace("http://www.w3.org/ns/prov#")

# ==========================
# OFFICIALS IMPORTS (per owl:imports)
# ==========================

IMPORT_MEMENTO  = URIRef("https://raw.githubusercontent.com/dfsantamaria/Memento/main/ontologies/memento-o.owl")
IMPORT_DYNDIFF  = URIRef("http://www.list.lu/change-ontology/")
IMPORT_PROVO    = URIRef("http://www.w3.org/ns/prov-o#")

# ==========================
# CREATE TIMESTAMP ISO 8601 Z
# ==========================

def iso_timestamp():
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

# ==========================
# PARSE VERSION STRING (X.Y.Z[-meta])
# ==========================

def parse_version(version_str: str):
    v = version_str.strip()

    if re.fullmatch(r"[A-Za-z0-9_]+", v):
        v = f"0.0.0-{v}"

    if re.fullmatch(r"\d+", v):
        v = f"{v}.0.0"
    elif re.fullmatch(r"\d+\.\d+", v):
        v = f"{v}.0"

    if "-" in v:
        numeric, metadata = v.split("-", 1)
    else:
        numeric, metadata = v, None

    parts = numeric.split(".")
    if len(parts) != 3:
        raise ValueError("La versione deve essere nel formato X.Y.Z[-meta]")

    major, minor, patch = map(int, parts)
    return major, minor, patch, metadata

# ==========================
# CREATE IRI STATE
# ==========================

def make_state_iri(base_uri: str, ontology_name: str, state_name: str) -> URIRef:
    return URIRef(f"{base_uri}/state/{ontology_name}/{state_name}")

# ==========================
# CREATE IRI CHANGE GRAPH
# ==========================

def make_ocg_iri(base_uri: str, ontology_name: str) -> URIRef:
    return URIRef(f"{base_uri}/ocg/{ontology_name}")

# ==========================
# CREATE IRI STATE GRAPH
# ==========================

def make_state_graph_iri(base_uri: str, ontology_name: str, state_name: str) -> URIRef:
    return URIRef(f"{base_uri}/graphs/{ontology_name}/state/{state_name}")

# ==========================
# CREATE OWL:AXIOM IRI (NO BNODE)
# ==========================

def make_axiom_iri(base_uri: str, ontology_name: str) -> URIRef:
    return URIRef(f"{base_uri}/axiom/{ontology_name}/{uuid4().hex}")

# ==========================
# CREATE FACTORY X CHANGE IRI
# ==========================

def make_change_iri(base_uri: str, ontology_name: str, ts: str, state_name: str, seq: int) -> URIRef:
    return URIRef(f"{base_uri}/change/{ontology_name}/{ontology_name}-{ts}-{state_name}-{seq:04d}")

# ==========================
# CREATE AXIOM BNODE
# ==========================
def add_axiom_bnode(state_graph: Graph, s, p, o):
    ax = BNode()
    state_graph.add((ax, RDF.type, OWL.Axiom))
    state_graph.add((ax, OWL.annotatedSource, s))
    state_graph.add((ax, OWL.annotatedProperty, p))
    state_graph.add((ax, OWL.annotatedTarget, o))
    return ax

# ==========================
# IMPORTS + HEADER STATO
# ==========================

def declare_imports_in_state_graph(state_graph: Graph, ontology_iri: URIRef):
    state_graph.add((ontology_iri, RDF.type, OWL.Ontology))
    state_graph.add((ontology_iri, OWL.imports, IMPORT_MEMENTO))
    state_graph.add((ontology_iri, OWL.imports, IMPORT_DYNDIFF))
    state_graph.add((ontology_iri, OWL.imports, IMPORT_PROVO))

    state_graph.add((MEMENTO.hasOntologyStateChange, RDF.type, OWL.AnnotationProperty))

    state_graph.add((MEMENTO.hasOntologyState, RDF.type, OWL.ObjectProperty))
    state_graph.add((MEMENTO.hasPreviousState, RDF.type, OWL.ObjectProperty))
    state_graph.add((MEMENTO.hasOntologyStateVersion, RDF.type, OWL.ObjectProperty))
    state_graph.add((PROV.wasGeneratedBy, RDF.type, OWL.ObjectProperty))

    state_graph.add((PROV.startedAtTime, RDF.type, OWL.DatatypeProperty))

def declare_version_dataprops(g: Graph):
    for dp in [
        MEMENTO.hasOntologyStateVersionLabel,
        MEMENTO.hasOntologyStateVersionMajorRevision,
        MEMENTO.hasOntologyStateVersionMinorRevision,
        MEMENTO.hasOntologyStateVersionPatchRevision,
        MEMENTO.hasOntologyStateVersionMetadata,
    ]:
        g.add((dp, RDF.type, OWL.DatatypeProperty))

def change_action_class(ch_type: URIRef) -> URIRef:
    if str(ch_type).split("/")[-1].startswith("add"):
        return MEMENTO.AddChangeAction
    if str(ch_type).split("/")[-1].startswith("del"):
        return MEMENTO.DelChangeAction
    return MEMENTO.AnyChangeAction

def is_system_triple(s, p, o, base_uri):

    """
    Returns True if the triple belongs to system-level metadata and
    must be excluded from semantic operations (diff, revert, state evolution).

    The function defines a global semantic boundary between
    ontology content and system-generated structures.
    """

    if isinstance(s, BNode):
        return True

    if p in (
        OWL.annotatedSource,
        OWL.annotatedProperty,
        OWL.annotatedTarget
    ):
        return True

    if p == RDF.type and o == OWL.Axiom:
        return True

    if str(p).startswith(str(MEMENTO)) or str(p).startswith(str(PROV)):
        return True

    if p in (OWL.imports,):
        return True

    if p == RDF.type and o not in (
        OWL.Class,
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
        OWL.NamedIndividual
    ):
        return True

    if isinstance(s, URIRef) and str(s).startswith(f"{base_uri}/axiom/"):
        return True

    return False

def get_or_create_axiom(g: Graph, base_uri: str, ontology_name: str, s, p, o):
    for ax in g.subjects(RDF.type, OWL.Axiom):
        if (ax, OWL.annotatedSource, s) in g and \
           (ax, OWL.annotatedProperty, p) in g and \
           (ax, OWL.annotatedTarget, o) in g:
            return ax

    axiom_iri = make_axiom_iri(base_uri, ontology_name)
    g.add((axiom_iri, RDF.type, OWL.Axiom))
    g.add((axiom_iri, OWL.annotatedSource, s))
    g.add((axiom_iri, OWL.annotatedProperty, p))
    g.add((axiom_iri, OWL.annotatedTarget, o))
    return axiom_iri

def copy_bnode_closure(src_g, dst_g, node):
    stack = [node]
    seen = set()

    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)

        for (s, p, o) in src_g.triples((n, None, None)):
            dst_g.add((s, p, o))
            if isinstance(o, BNode):
                stack.append(o)

        for (s, p, o) in src_g.triples((None, None, n)):
            dst_g.add((s, p, o))
            if isinstance(s, BNode):
                stack.append(s)

def entity_exists_in_state(g: Graph, entity, base_uri: str) -> bool:
    for (s, p, o) in g.triples((entity, None, None)):
        if not is_system_triple(s, p, o, base_uri):
            return True
    return False

def get_named_superclasses(g: Graph, cls):
    out = set()
    stack = [cls]
    seen = set()

    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)

        for sup in g.objects(cur, RDFS.subClassOf):
            if isinstance(sup, URIRef) and sup not in out:
                out.add(sup)
                stack.append(sup)

    return out

def propagate_change_to_anonymous_ancestor_equivs(search_g: Graph, target_g: Graph, cls, ch_iri):
    ancestors = get_named_superclasses(search_g, cls)

    cls_changes = list(target_g.objects(cls, MEMENTO.hasOntologyStateChange))

    for anc in ancestors:
        for ax in target_g.subjects(RDF.type, OWL.Axiom):
            src = next(target_g.objects(ax, OWL.annotatedSource), None)
            prop = next(target_g.objects(ax, OWL.annotatedProperty), None)
            tgt = next(target_g.objects(ax, OWL.annotatedTarget), None)

            if src != anc:
                continue
            if prop not in (OWL.equivalentClass, RDFS.subClassOf):
                continue
            if not isinstance(tgt, BNode):
                continue

            ax_changes = list(target_g.objects(ax, MEMENTO.hasOntologyStateChange))
            all_changes = set(ax_changes) | set(cls_changes) | {ch_iri}

            for ch in all_changes:
                target_g.add((ax, MEMENTO.hasOntologyStateChange, ch))

def rdf_list_items(g: Graph, head):
    items = []
    while head and head != RDF.nil:
        first = next(g.objects(head, RDF.first), None)
        rest  = next(g.objects(head, RDF.rest), None)
        if first is None:
            break
        items.append(first)
        head = rest
    return items

def expand_all_disjoint_classes(g: Graph):
    pairs = []

    for adc in g.subjects(RDF.type, OWL.AllDisjointClasses):

        members = next(g.objects(adc, OWL.members), None)
        if members is None:
            continue

        items = rdf_list_items(g, members)

        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a = items[i]
                b = items[j]

                if isinstance(a, URIRef) and isinstance(b, URIRef):
                    pairs.append((a, OWL.disjointWith, b))

    return pairs

# ================================================================
# MEMENTO-SM — MODULE 2
# Store Wrapper + MementoSM Skeleton
# ================================================================

class VirtuosoStoreWrapper:
    """
    Wrapper compatible with:
    - In-memory RDFLib (ConjunctiveGraph)
    - Virtuoso via SPARQLUpdateStore
    """
    def __init__(self, store=None, query_endpoint=None, update_endpoint=None):

        if store is not None and hasattr(store, "get_context"):
            self.store = store
            return

        if query_endpoint and update_endpoint:
            s = SPARQLUpdateStore(
                queryEndpoint=query_endpoint,
                updateEndpoint=update_endpoint,
                auth=("dba", "dba")   
            )
            s.open((query_endpoint, update_endpoint))
            self.store = s
        else:
            cg = ConjunctiveGraph()
            self.store = cg.store

    def get_context(self, iri):
        return Graph(store=self.store, identifier=URIRef(str(iri)))

    def remove_context(self, iri):
        giri = URIRef(str(iri))
        if isinstance(self.store, SPARQLUpdateStore):
            Graph(store=self.store).update(f"CLEAR GRAPH <{giri}>")
        else:
            ctx = Graph(store=self.store, identifier=giri)
            ctx.remove((None, None, None))

    def contexts(self):
        if isinstance(self.store, SPARQLUpdateStore):
            g = Graph(store=self.store)
            q = "SELECT DISTINCT ?g WHERE { GRAPH ?g { ?s ?p ?o } }"
            res = g.query(q)
            return [Graph(store=self.store, identifier=row.g) for row in res]
        else:
            cg = ConjunctiveGraph(store=self.store)
            return list(cg.contexts())

    def persist(self):
        return

# ================================================================
# MAIN CLASS: MEMENTO-SM
# ================================================================

class MementoSM:
    def __init__(
        self,
        store=None,
        base_graph_uri="http://example.org/memento",
        virtuoso_query_endpoint=None,
        virtuoso_update_endpoint=None
    ):

        if store is not None and hasattr(store, "get_context"):
            self.store = store
        else:
            self.store = VirtuosoStoreWrapper(
                query_endpoint=virtuoso_query_endpoint,
                update_endpoint=virtuoso_update_endpoint
            )

        self.base = base_graph_uri
        self.meta_graph_iri = URIRef(f"{self.base}/meta")

        meta = self.store.get_context(self.meta_graph_iri)

        meta.add((MEMENTO.hasOntologyStateChange, RDF.type, OWL.AnnotationProperty))
        meta.add((MEMENTO.hasOntologyState, RDF.type, OWL.ObjectProperty))
        meta.add((MEMENTO.hasPreviousState, RDF.type, OWL.ObjectProperty))
        meta.add((MEMENTO.hasOntologyStateVersion, RDF.type, OWL.ObjectProperty))
        meta.add((PROV.wasGeneratedBy, RDF.type, OWL.ObjectProperty))
        meta.add((PROV.startedAtTime, RDF.type, OWL.DatatypeProperty))

        GITHUB_BASE = "https://raw.githubusercontent.com/dfsantamaria/Memento/main/ontologies"

        self._memento_url = f"{GITHUB_BASE}/memento-o.owl"
        self._dyndiff_url = "http://www.list.lu/change-ontology/"
        self._prov_url     = f"{GITHUB_BASE}/prov-o.ttl"

        meta = self.store.get_context(self.meta_graph_iri)
        meta.remove((None, None, None))

        try:
            meta.parse(self._memento_url, format="xml")       
            meta.parse(self._prov_url, format="turtle")       
            meta.parse(self._dyndiff_url, format="turtle")      

            print("✓ Base ontologies uploaded successfully from GitHub")
        except Exception as e:
            print("Error loading ontologies from GitHub:", e)

        meta.add((MEMENTO.hasOntologyStateChange, RDF.type, OWL.AnnotationProperty))
        meta.add((MEMENTO.hasOntologyState, RDF.type, OWL.ObjectProperty))
        meta.add((MEMENTO.hasPreviousState, RDF.type, OWL.ObjectProperty))
        meta.add((MEMENTO.hasOntologyStateVersion, RDF.type, OWL.ObjectProperty))
        meta.add((PROV.wasGeneratedBy, RDF.type, OWL.ObjectProperty))
        meta.add((PROV.startedAtTime, RDF.type, OWL.DatatypeProperty))

    # ================================================================
    # UTILITY
    # ================================================================

    def _state_iri(self, ontology_name, state_name):
        return make_state_iri(self.base, ontology_name, state_name)

    def _ocg_iri(self, ontology_name):
        return make_ocg_iri(self.base, ontology_name)

    def _state_graph_iri(self, ontology_name, state_name):
        return make_state_graph_iri(self.base, ontology_name, state_name)

    def get_ontology_state(self, ontology_name, state_name):
        return self.store.get_context(self._state_graph_iri(ontology_name, state_name))

    def get_ontology_states(self, ontology_name):
        """
        Sort states by the PROV:startedAtTime timestamp in the meta graph.
        """
        prefix = f"{self.base}/graphs/{ontology_name}/state/"
        found = []
        meta = self.store.get_context(self.meta_graph_iri)

        for ctx in self.store.contexts():
            uri = str(ctx.identifier)
            if uri.startswith(prefix):
                sname = uri.split("/")[-1]
                state_iri = self._state_iri(ontology_name, sname)
                tvals = list(meta.objects(state_iri, PROV.startedAtTime))
                ts = str(tvals[0]) if tvals else ""
                found.append((sname, ts))

        found.sort(key=lambda x: x[1])
        return [s for s, _ in found]

    def last_state_iri(self, ontology_name):
        states = self.get_ontology_states(ontology_name)
        if not states:
            return None
        return self._state_iri(ontology_name, states[-1])

# ================================================================
# MEMENTO-SM — MODULE 3
# create_ontology() 
# ================================================================

    def create_ontology(
        self,
        ontology_name: str,
        graph_or_path,
        state_name: str,
        author_name: str,
        version="1.0",
        fmt=None
    ):
        """ 
        Creates the initial ontology snapshot (state s0).

        The input ontology is imported and normalized into a state graph,
        while all changes are materialized as OntologyStateChange entities
        according to the MEMENTO model.

        This method corresponds to the initialization phase described in
        Section X of the paper. 
        """
        
        # LOAD
        g_in = graph_or_path if isinstance(graph_or_path, Graph) else Graph()
        if not isinstance(graph_or_path, Graph):
            if fmt:
                g_in.parse(graph_or_path, format=fmt)
            else:
                g_in.parse(graph_or_path)

        # ------------------------------------
        # EXPAND owl:AllDisjointClasses
        # ------------------------------------

        for (s,p,o) in expand_all_disjoint_classes(g_in):
            g_in.add((s,p,o))

        # GRAPHS
        state_iri = self._state_iri(ontology_name, state_name)
        ocg = self.store.get_context(self._ocg_iri(ontology_name))
        meta = self.store.get_context(self.meta_graph_iri)
        state_graph = self.store.get_context(self._state_graph_iri(ontology_name, state_name))

        agent_iri = URIRef(f"{self.base}/agent/{author_name.replace(' ', '_')}")

        # ONTOLOGY IRI
        ontology_iri = None
        for s in g_in.subjects(RDF.type, OWL.Ontology):
            ontology_iri = s
            break
        if ontology_iri is None:
            ontology_iri = URIRef(f"http://example.org/ontology/{ontology_name}")

        # HEADER AND IMPORTS
        declare_imports_in_state_graph(state_graph, ontology_iri)
        for pfx, ns in [
            ("rdf", RDF), ("rdfs", RDFS), ("owl", OWL), ("xsd", XSD),
            ("memento", MEMENTO), ("prov", PROV), ("dyn", DYNDIFF)
        ]:
            state_graph.bind(pfx, ns)

        state_graph.bind("skos", Namespace("http://www.w3.org/2004/02/skos/core#"))

        declare_version_dataprops(state_graph)

        ANNOTATION_PROPS = {
            RDFS.comment,
            RDFS.label,
            OWL.versionInfo,
            OWL.priorVersion,
            OWL.backwardCompatibleWith,
            OWL.incompatibleWith
        }

        ANNOTATION_PROPS |= set(g_in.subjects(RDF.type, OWL.AnnotationProperty))

        filtered = []

        for (s, p, o) in set(g_in):

            if p == RDF.type and o == OWL.Ontology:
                continue

            state_graph.add((s, p, o))

            if p not in ANNOTATION_PROPS:
                filtered.append((s, p, o))

            if isinstance(o, BNode):
                copy_bnode_closure(g_in, state_graph, o)

        # ------------------------------------
        # COPY ANNOTATION AXIOMS 
        # ------------------------------------
        for ax in g_in.subjects(RDF.type, OWL.Axiom):

            src = list(g_in.objects(ax, OWL.annotatedSource))
            prop = list(g_in.objects(ax, OWL.annotatedProperty))
            tgt = list(g_in.objects(ax, OWL.annotatedTarget))

            if not (src and prop and tgt):
                continue

            ax_state = add_axiom_bnode(state_graph, src[0], prop[0], tgt[0])

            for (a_s, a_p, a_o) in g_in.triples((ax, None, None)):
                if a_p not in (
                    RDF.type,
                    OWL.annotatedSource,
                    OWL.annotatedProperty,
                    OWL.annotatedTarget
                ):
                    state_graph.add((ax_state, a_p, a_o))

        ts = iso_timestamp()
        ts_lit = Literal(ts, datatype=XSD.dateTime)

        # --------------------------
        # FILTER VALID CHANGES
        # --------------------------

        entity_to_change = {}
        ent_seq = 0

        seen_triples = set()

        for (s, p, o) in filtered:

            if not (
                (s, RDF.type, OWL.Class) in g_in or
                (s, RDF.type, OWL.ObjectProperty) in g_in or
                (s, RDF.type, OWL.DatatypeProperty) in g_in or
                (s, RDF.type, OWL.AnnotationProperty) in g_in or
                (s, RDF.type, OWL.NamedIndividual) in g_in
            ):
                continue

            triple = (s, p, o)

            if triple in seen_triples:
                continue
            seen_triples.add(triple)

            if p in (
                OWL.equivalentClass,
                OWL.equivalentProperty
            ):
                continue

            if p in (
                RDFS.label,
                RDFS.comment,
                OWL.versionInfo
            ):
                continue

            if p in (
                OWL.equivalentClass,
                RDFS.subClassOf,
                OWL.equivalentProperty,
                RDFS.subPropertyOf,
                RDFS.domain,
                RDFS.range,
                OWL.disjointWith
            ):
                pass

            elif p == RDF.type:
                pass

            else:
                continue

            if s not in entity_to_change:
                ent_seq += 1
                entity_to_change[s] = make_change_iri(
                    self.base, ontology_name, ts, state_name, ent_seq
                )

        for ent, ch_iri in entity_to_change.items():
            if (ent, RDF.type, OWL.Class) in g_in:
                ch_type = DYNDIFF.addC
            elif (
                (ent, RDF.type, OWL.ObjectProperty) in g_in or
                (ent, RDF.type, OWL.DatatypeProperty) in g_in or
                (ent, RDF.type, OWL.AnnotationProperty) in g_in
            ):
                ch_type = DYNDIFF.addP
            else:
                ch_type = DYNDIFF.addI

            # OCG
            ocg.add((ch_iri, RDF.type, change_action_class(ch_type)))
            ocg.add((ch_iri, MEMENTO.hasOntologyState, state_iri))

            # STATE GRAPH
            state_graph.add((ch_iri, RDF.type, change_action_class(ch_type)))
            state_graph.add((ch_iri, MEMENTO.hasOntologyState, state_iri))

            state_graph.set((ent, MEMENTO.hasOntologyStateChange, ch_iri))

        # ------------------------------------
        # REIFY AllDisjointClasses AXIOMS
        # ------------------------------------

        for adc in g_in.subjects(RDF.type, OWL.AllDisjointClasses):

            members = next(g_in.objects(adc, OWL.members), None)
            if members is None:
                continue

            axiom_iri = make_axiom_iri(self.base, ontology_name)
            ocg.add((axiom_iri, RDF.type, OWL.Axiom))
            ocg.add((axiom_iri, OWL.annotatedSource, s))
            ocg.add((axiom_iri, OWL.annotatedProperty, p))
            ocg.add((axiom_iri, OWL.annotatedTarget, o))
            ocg.add((axiom_iri, MEMENTO.hasOntologyStateChange, ch_iri))

            ax_state = get_or_create_axiom(
                state_graph,
                self.base,
                ontology_name,
                adc,
                OWL.members,
                members
            )

        # --------------------------
        # REIFICATION AXIOMS 
        # --------------------------

        for (s, p, o) in filtered:

            # ------------------------------------
            # REIFY INSTANCE ASSERTIONS
            # ------------------------------------

            if p == RDF.type and isinstance(s, URIRef) and isinstance(o, URIRef) and o != OWL.NamedIndividual:

                axiom_iri = get_or_create_axiom(ocg, self.base, ontology_name, s, RDF.type, o)
                if s in entity_to_change:
                    ocg.add((axiom_iri, MEMENTO.hasOntologyStateChange, entity_to_change[s]))

                ax_state = get_or_create_axiom(
                    state_graph,
                    self.base,
                    ontology_name,
                    s,
                    p,
                    o
                )

                if s in entity_to_change:
                    state_graph.add((ax_state, MEMENTO.hasOntologyStateChange, entity_to_change[s]))

                continue

            # --------------------------
            # REIFICATION AXIOMS 
            # --------------------------

            if p not in (
                RDFS.subClassOf,
                OWL.equivalentClass,
                OWL.disjointWith
            ):
                continue

            if isinstance(o, BNode):

                copy_bnode_closure(g_in, state_graph, o)

                axiom_iri = get_or_create_axiom(
                    state_graph,
                    self.base,
                    ontology_name,
                    s,
                    p,
                    o
                )

                axiom_iri_ocg = get_or_create_axiom(
                    ocg,
                    self.base,
                    ontology_name,
                    s,
                    p,
                    o
                )

                if p != OWL.equivalentClass:
                    if s in entity_to_change:
                        state_graph.add((axiom_iri, MEMENTO.hasOntologyStateChange, entity_to_change[s]))

                    if s in entity_to_change:
                        ocg.add((axiom_iri_ocg, MEMENTO.hasOntologyStateChange, entity_to_change[s]))

                continue

            axiom_iri = get_or_create_axiom(
                ocg,
                self.base,
                ontology_name,
                s,
                p,
                o
            )

            ax_state = get_or_create_axiom(
                state_graph,
                self.base,
                ontology_name,
                s,
                p,
                o
            )

            if p != OWL.equivalentClass:
                if s in entity_to_change:
                    state_graph.add((ax_state, MEMENTO.hasOntologyStateChange, entity_to_change[s]))
                    
            if s in entity_to_change:
                ocg.add((axiom_iri, MEMENTO.hasOntologyStateChange, entity_to_change[s]))

            if s in entity_to_change:
                ocg.add((
                    axiom_iri,
                    MEMENTO.hasOntologyStateChange,
                    entity_to_change[s]
                ))

        version_iri = URIRef(f"{self.base}/version/{ontology_name}/{state_name}-version-{version}")
        now = ts_lit

        meta.add((state_iri, RDF.type, MEMENTO.OntologyState))
        meta.add((state_iri, PROV.startedAtTime, now))
        meta.add((state_iri, PROV.wasGeneratedBy, agent_iri))
        meta.add((state_iri, MEMENTO.hasOntologyStateVersion, version_iri))

        #VERSION PARSING
        major, minor, patch, metadata = parse_version(version)

        meta.add((version_iri, RDF.type, MEMENTO.OntologyStateVersion))

        meta.add((
            version_iri,
            MEMENTO.hasOntologyStateVersionLabel,
            Literal(version, datatype=XSD.string)
        ))

        meta.add((
            version_iri,
            MEMENTO.hasOntologyStateVersionMajorRevision,
            Literal(major, datatype=XSD.integer)
        ))
        meta.add((
            version_iri,
            MEMENTO.hasOntologyStateVersionMinorRevision,
            Literal(minor, datatype=XSD.integer)
        ))
        meta.add((
            version_iri,
            MEMENTO.hasOntologyStateVersionPatchRevision,
            Literal(patch, datatype=XSD.integer)
        ))

        if metadata:
            meta.add((
                version_iri,
                MEMENTO.hasOntologyStateVersionMetadata,
                Literal(metadata, datatype=XSD.string)
            ))

        meta.add((agent_iri, RDF.type, PROV.Agent))
        meta.add((agent_iri, RDF.type, PROV.Person))

        #MIRROR INTO STATE GRAPH
        state_graph.add((state_iri, RDF.type, MEMENTO.OntologyState))
        state_graph.add((state_iri, PROV.startedAtTime, now))
        state_graph.add((state_iri, MEMENTO.hasOntologyStateVersion, version_iri))
        state_graph.add((state_iri, PROV.wasGeneratedBy, agent_iri))

        state_graph.add((version_iri, RDF.type, MEMENTO.OntologyStateVersion))
        state_graph.add((
            version_iri,
            MEMENTO.hasOntologyStateVersionLabel,
            Literal(version, datatype=XSD.string)
        ))
        state_graph.add((
            version_iri,
            MEMENTO.hasOntologyStateVersionMajorRevision,
            Literal(major, datatype=XSD.integer)
        ))
        state_graph.add((
            version_iri,
            MEMENTO.hasOntologyStateVersionMinorRevision,
            Literal(minor, datatype=XSD.integer)
        ))
        state_graph.add((
            version_iri,
            MEMENTO.hasOntologyStateVersionPatchRevision,
            Literal(patch, datatype=XSD.integer)
        ))
        if metadata:
            state_graph.add((
                version_iri,
                MEMENTO.hasOntologyStateVersionMetadata,
                Literal(metadata, datatype=XSD.string)
            ))

        self.store.persist()
        return state_iri

# ================================================================
# MEMENTO-SM — MODULE 4
# create_ontology_state(), revert_ontology(), diff, remove
# ================================================================

    def create_ontology_state(
        self,
        ontology_name: str,
        changes: list,
        previous_state=None,
        state_name: str = None,
        author: str = None,
        version="1.0",
        prev_state_name=None,
        bulk=False
    ):
        """
        Creates a new ontology state by applying a set of atomic changes
        (additions or deletions) to a previous state.

        Each change is reified as an OWL Axiom and linked to exactly one
        OntologyStateChange entity. Optionally, multiple changes of the
        same type can be grouped using bulk mode.

        This method implements the state evolution mechanism defined in
        the MEMENTO-SM model.
        """

        """
        bulk = bool
        If True, changes of the same type are grouped into a single
        OntologyStateChange entity, following the bulk strategy
        described in the paper.
        """

        meta = self.store.get_context(self.meta_graph_iri)
        ocg = self.store.get_context(self._ocg_iri(ontology_name))

        agent_iri = URIRef(f"{self.base}/agent/{author.replace(' ', '_')}")
        new_state_iri = self._state_iri(ontology_name, state_name)
        new_state_graph = self.store.get_context(self._state_graph_iri(ontology_name, state_name))

        ts = iso_timestamp()
        ts_literal = Literal(ts, datatype=XSD.dateTime)

        if previous_state is not None:
            prev_state_name = previous_state

        # --------------------------
        # FILTER VALID CHANGES 
        # --------------------------

        changes = [
            ((s, p, o), t)
            for ((s, p, o), t) in changes
            if not is_system_triple(s, p, o, self.base)
        ]

        incoming_change_graph = Graph()
        for (s, p, o), _ in changes:
            incoming_change_graph.add((s, p, o))

        ontology_iri = None
        first_states = self.get_ontology_states(ontology_name)
        if first_states:
            g0 = self.get_ontology_state(ontology_name, first_states[0])
            for s in g0.subjects(RDF.type, OWL.Ontology):
                ontology_iri = s
                break
        if ontology_iri is None:
            ontology_iri = URIRef(f"http://example.org/ontology/{ontology_name}")

        if prev_state_name is None:
            states = self.get_ontology_states(ontology_name)
            prev_state_name = states[-1] if states else None

        prev_ctx = None
        if prev_state_name:
            prev_ctx = self.get_ontology_state(ontology_name, prev_state_name)

        prev_triples = set(prev_ctx) if prev_ctx else set()

        # --------------------------
        # HEADER + IMPORTS
        # --------------------------

        declare_imports_in_state_graph(new_state_graph, ontology_iri)
        for pfx, ns in [
            ("rdf", RDF), ("rdfs", RDFS), ("owl", OWL), ("xsd", XSD),
            ("memento", MEMENTO), ("prov", PROV), ("dyn", DYNDIFF)
        ]:
            new_state_graph.bind(pfx, ns)

        declare_version_dataprops(new_state_graph)

        # --------------------------
        # COPY PREVIOUS STATE 
        # --------------------------

        if prev_state_name:
            prev_ctx = self.get_ontology_state(ontology_name, prev_state_name)

            for t in prev_ctx:
                new_state_graph.add(t)

        for ax in list(new_state_graph.subjects(RDF.type, OWL.Axiom)):

            ax_changes = list(new_state_graph.objects(ax, MEMENTO.hasOntologyStateChange))

            if len(ax_changes) > len(set(ax_changes)):
                new_state_graph.remove((ax, MEMENTO.hasOntologyStateChange, None))
                for ch in set(ax_changes):
                    new_state_graph.add((ax, MEMENTO.hasOntologyStateChange, ch))

        # --------------------------
        # METADATA
        # --------------------------

        version_iri = URIRef(f"{self.base}/version/{ontology_name}/{state_name}-version-{version}")

        major, minor, patch, metadata = parse_version(version)

        meta.add((version_iri, RDF.type, MEMENTO.OntologyStateVersion))
        meta.add((version_iri, MEMENTO.hasOntologyStateVersionLabel,
                Literal(version, datatype=XSD.string)))
        meta.add((version_iri, MEMENTO.hasOntologyStateVersionMajorRevision,
                Literal(major, datatype=XSD.integer)))
        meta.add((version_iri, MEMENTO.hasOntologyStateVersionMinorRevision,
                Literal(minor, datatype=XSD.integer)))
        meta.add((version_iri, MEMENTO.hasOntologyStateVersionPatchRevision,
                Literal(patch, datatype=XSD.integer)))

        if metadata:
            meta.add((version_iri, MEMENTO.hasOntologyStateVersionMetadata,
                    Literal(metadata, datatype=XSD.string)))

        meta.add((new_state_iri, RDF.type, MEMENTO.OntologyState))
        meta.add((new_state_iri, PROV.startedAtTime, ts_literal))
        meta.add((new_state_iri, PROV.wasGeneratedBy, agent_iri))
        meta.add((new_state_iri, MEMENTO.hasOntologyStateVersion, version_iri))

        if prev_state_name is not None:
            prev_state_iri = self._state_iri(ontology_name, prev_state_name)
            meta.add((new_state_iri, MEMENTO.hasPreviousState, prev_state_iri))

        meta.add((version_iri, RDF.type, MEMENTO.OntologyStateVersion))

        meta.add((agent_iri, RDF.type, PROV.Agent))
        meta.add((agent_iri, RDF.type, PROV.Person))

        new_state_graph.add((new_state_iri, RDF.type, MEMENTO.OntologyState))
        new_state_graph.add((new_state_iri, PROV.startedAtTime, ts_literal))
        new_state_graph.add((new_state_iri, MEMENTO.hasOntologyStateVersion, version_iri))
        new_state_graph.add((new_state_iri, PROV.wasGeneratedBy, agent_iri))

        if prev_state_name is not None:
            prev_state_iri = self._state_iri(ontology_name, prev_state_name)
            new_state_graph.add((new_state_iri, MEMENTO.hasPreviousState, prev_state_iri))

        new_state_graph.add((version_iri, RDF.type, MEMENTO.OntologyStateVersion))

        new_state_graph.add((
            version_iri,
            MEMENTO.hasOntologyStateVersionLabel,
            Literal(version, datatype=XSD.string)
        ))
        new_state_graph.add((
            version_iri,
            MEMENTO.hasOntologyStateVersionMajorRevision,
            Literal(major, datatype=XSD.integer)
        ))
        new_state_graph.add((
            version_iri,
            MEMENTO.hasOntologyStateVersionMinorRevision,
            Literal(minor, datatype=XSD.integer)
        ))
        new_state_graph.add((
            version_iri,
            MEMENTO.hasOntologyStateVersionPatchRevision,
            Literal(patch, datatype=XSD.integer)
        ))
        if metadata:
            new_state_graph.add((
                version_iri,
                MEMENTO.hasOntologyStateVersionMetadata,
                Literal(metadata, datatype=XSD.string)
            ))

        new_state_graph.add((MEMENTO.hasOntologyState, RDF.type, OWL.AnnotationProperty))
        new_state_graph.add((MEMENTO.hasOntologyStateChange, RDF.type, OWL.AnnotationProperty))

        # --------------------------
        # BULK X CHANGE TYPE
        # --------------------------

        bulk_seq = 0

        bulk_iris = {}
        for (_, ch_type) in changes:
            if ch_type not in bulk_iris:
                bulk_seq += 1
                iri = make_change_iri(self.base, ontology_name, ts, state_name, bulk_seq)
                bulk_iris[ch_type] = iri

                ocg.add((iri, RDF.type, ch_type))
                ocg.add((iri, RDF.type, DYNDIFF.BasicChange))
                ocg.add((iri, RDF.type, PROV.Entity))
                ocg.add((iri, RDF.type, change_action_class(ch_type)))
                ocg.add((iri, PROV.startedAtTime, ts_literal))
                ocg.add((iri, PROV.wasGeneratedBy, agent_iri))
                ocg.add((iri, MEMENTO.hasOntologyState, new_state_iri))
                ocg.add((iri, RDF.type, MEMENTO.OntologyStateChange))

        change_seq = 0
        entity_change = {}

        for (s, p, o), ch_type in changes:

            if ch_type in (DYNDIFF.addC, DYNDIFF.addI, DYNDIFF.addP):
                if p == RDFS.subClassOf and isinstance(o, BNode):
                    pass
                else:
                    if (s, p, o) in prev_triples:
                        continue

            if not isinstance(s, URIRef):
                continue

            if ch_type == DYNDIFF.addC:
                if (s, RDF.type, OWL.Class) not in new_state_graph:
                    new_state_graph.add((s, RDF.type, OWL.Class))

            elif ch_type in (DYNDIFF.addI, DYNDIFF.addP):
                if (s, p, o) not in new_state_graph:
                    new_state_graph.add((s, p, o))

            elif ch_type == DYNDIFF.delC:

                removed_triples = list(new_state_graph.triples((s, None, None)))

                for triple in removed_triples:
                    _, pred, obj = triple

                    if pred in (
                        MEMENTO.hasOntologyStateChange,
                        RDF.type,
                        RDFS.label,
                        RDFS.comment,
                        RDFS.isDefinedBy,
                        OWL.versionInfo,
                        OWL.annotatedSource,
                        OWL.annotatedProperty,
                        OWL.annotatedTarget
                    ):
                        continue

                    new_state_graph.remove(triple)

        # --------------------------
        # DELTA + AXIOMS
        # --------------------------

        for (s, p, o), ch_type in changes:

            if p in (RDFS.label, RDFS.comment, OWL.versionInfo):
                if ch_type not in (DYNDIFF.addI, DYNDIFF.addP):
                    continue

                if prev_ctx is not None and (s, p, o) in prev_ctx:
                    continue

                if (s, p, o) not in new_state_graph:
                    new_state_graph.add((s, p, o))

            if not isinstance(s, URIRef):
                continue

            if s not in entity_change:
                change_seq += 1
                ch_iri = make_change_iri(self.base, ontology_name, ts, state_name, change_seq)
                entity_change[s] = ch_iri

                action_cls = change_action_class(ch_type)

                ocg.add((ch_iri, RDF.type, action_cls))
                ocg.add((ch_iri, MEMENTO.hasOntologyState, new_state_iri))

                new_state_graph.add((ch_iri, RDF.type, action_cls))
                new_state_graph.add((ch_iri, MEMENTO.hasOntologyState, new_state_iri))

                entity_was_in_prev = (
                    prev_ctx is not None and entity_exists_in_state(prev_ctx, s, self.base)
                )

                if not entity_was_in_prev:
                    new_state_graph.remove((s, MEMENTO.hasOntologyStateChange, None))

                    for ax_old in list(new_state_graph.subjects(OWL.annotatedSource, s)):
                        for ch in list(new_state_graph.objects(ax_old, MEMENTO.hasOntologyStateChange)):
                            if (ch, MEMENTO.hasOntologyState, new_state_iri) in new_state_graph:
                                new_state_graph.remove((ax_old, MEMENTO.hasOntologyStateChange, ch))

                new_state_graph.add((s, MEMENTO.hasOntologyStateChange, ch_iri))

            ch_iri = entity_change[s]

            for ap in (RDFS.label, RDFS.comment, OWL.versionInfo):
                for ao in new_state_graph.objects(s, ap):

                    ax_ann = get_or_create_axiom(
                        new_state_graph,
                        self.base,
                        ontology_name,
                        s,
                        ap,
                        ao
                    )

                    new_state_graph.add((ax_ann, MEMENTO.hasOntologyStateChange, ch_iri))

            for ax in new_state_graph.subjects(RDF.type, OWL.Axiom):

                src = next(new_state_graph.objects(ax, OWL.annotatedSource), None)
                prop = next(new_state_graph.objects(ax, OWL.annotatedProperty), None)
                tgt = next(new_state_graph.objects(ax, OWL.annotatedTarget), None)
                ax_changes = list(new_state_graph.objects(ax, MEMENTO.hasOntologyStateChange))

                if prop == RDFS.subClassOf and isinstance(tgt, BNode):

                    if (ax, MEMENTO.hasOntologyStateChange, ch_iri) not in new_state_graph:
                        new_state_graph.add((ax, MEMENTO.hasOntologyStateChange, ch_iri))

            if ch_type in (DYNDIFF.delC, DYNDIFF.delI, DYNDIFF.delP):

                axiom_iri = get_or_create_axiom(ocg, self.base, ontology_name, s, p, o)
                ocg.add((axiom_iri, MEMENTO.hasOntologyStateChange, ch_iri))

            ax_state = None

            for ax in new_state_graph.subjects(OWL.annotatedSource, s):

                prop = next(new_state_graph.objects(ax, OWL.annotatedProperty), None)
                tgt  = next(new_state_graph.objects(ax, OWL.annotatedTarget), None)

                if prop != p:
                    continue

                if isinstance(tgt, BNode) and isinstance(o, BNode):

                    tgt_triples = set(new_state_graph.triples((tgt, None, None)))
                    o_triples   = set(new_state_graph.triples((o, None, None)))

                    if tgt_triples == o_triples:
                        ax_state = ax
                        break

                if tgt == o:
                    ax_state = ax
                    break


            if ax_state is not None:

                new_state_graph.add((ax_state, MEMENTO.hasOntologyStateChange, ch_iri))

                new_state_graph.add((s, MEMENTO.hasOntologyStateChange, ch_iri))

            else:
                axiom_iri = get_or_create_axiom(
                    ocg,
                    self.base,
                    ontology_name,
                    s,
                    p,
                    o
                )
                ocg.add((axiom_iri, MEMENTO.hasOntologyStateChange, ch_iri))

                if isinstance(o, BNode):

                    if ch_type in (DYNDIFF.delC, DYNDIFF.delI, DYNDIFF.delP):
                        bnode_source = prev_ctx if prev_ctx is not None else new_state_graph
                    else:
                        bnode_source = incoming_change_graph

                    copy_bnode_closure(bnode_source, new_state_graph, o)

                    if (o, RDF.type, OWL.Restriction) in bnode_source:
                        new_state_graph.add((o, RDF.type, OWL.Restriction))

                    ax_state = None

                    for ax in new_state_graph.subjects(RDF.type, OWL.Axiom):

                        src = next(new_state_graph.objects(ax, OWL.annotatedSource), None)
                        prop = next(new_state_graph.objects(ax, OWL.annotatedProperty), None)
                        tgt = next(new_state_graph.objects(ax, OWL.annotatedTarget), None)

                        if src == s and prop == p:

                            if isinstance(tgt, BNode) and isinstance(o, BNode):

                                tgt_triples = set(new_state_graph.triples((tgt, None, None)))
                                o_triples   = set(new_state_graph.triples((o, None, None)))

                                if tgt_triples == o_triples:
                                    ax_state = ax
                                    break

                            if tgt == o:
                                ax_state = ax
                                break

                    if ax_state is None:
                        ax_state = add_axiom_bnode(new_state_graph, s, p, o)

                    new_state_graph.add((ax_state, MEMENTO.hasOntologyStateChange, ch_iri))

                else:
                    ax_state = get_or_create_axiom(
                        new_state_graph,
                        self.base,
                        ontology_name,
                        s,
                        p,
                        o
                    )
                    new_state_graph.add((ax_state, MEMENTO.hasOntologyStateChange, ch_iri))

        for s in entity_change:

            ch_iri = entity_change[s]

            if (ch_iri, RDF.type, MEMENTO.DelChangeAction) in new_state_graph:
                search_graph = prev_ctx if prev_ctx is not None else new_state_graph
            else:
                search_graph = new_state_graph

            propagate_change_to_anonymous_ancestor_equivs(
                search_graph,
                new_state_graph,
                s,
                ch_iri
            )

            propagate_change_to_anonymous_ancestor_equivs(
                search_graph,
                ocg,
                s,
                ch_iri
            )

        self.store.persist()
        return new_state_iri

    # ================================================================
    # GET_ONTOLOGY_STATE_DIFF 
    # ================================================================

    @staticmethod
    def is_content_triple(s, p, o):

        """ 
        Returns True if the triple represents actual ontological content,
        i.e., TBox axioms, ABox assertions, or user-defined annotations.

        All provenance-related metadata, reification artifacts, versioning
        information, and system-generated triples are explicitly excluded.

        This function defines the semantic boundary used by diff, revert,
        and equivalence checking operations.
        """

        if isinstance(s, BNode):
            return False

        if p in (
            OWL.annotatedSource,
            OWL.annotatedProperty,
            OWL.annotatedTarget
        ):
            return False

        if p == RDF.type and o == OWL.Axiom:
            return False

        if str(p).startswith(str(MEMENTO)) or str(p).startswith(str(PROV)):
            return False

        if isinstance(o, BNode) and p == RDFS.subClassOf:
            return True

        if p == RDF.type and o in (
            MEMENTO.OntologyState,
            MEMENTO.OntologyStateVersion,
            MEMENTO.OntologyStateChange,
            PROV.Agent,
            PROV.Person
        ):
            return False

        if isinstance(s, URIRef) and (
            "/state/" in str(s)
            or "/version/" in str(s)
            or "/change/" in str(s)
            or "/axiom/" in str(s)
        ):
            return False

        return True
    
    def get_ontology_state_diff(self, ontology_name: str, state1: str, state2: str):

        """
        Computes the semantic difference between two ontology states.

        The comparison is performed exclusively on ontological content
        triples, ignoring all system metadata and provenance annotations.

        The result consists of added and removed triples, each associated
        with the OntologyStateChange that introduced or removed it.
        """

        g1 = self.get_ontology_state(ontology_name, state1)
        g2 = self.get_ontology_state(ontology_name, state2)
        ocg = self.store.get_context(self._ocg_iri(ontology_name))

        s2_iri = self._state_iri(ontology_name, state2)

        pure1 = {
            (s, p, o)
            for (s, p, o) in g1
            if self.is_content_triple(s, p, o)
        }

        pure2 = {
            (s, p, o)
            for (s, p, o) in g2
            if self.is_content_triple(s, p, o)
        }

        raw_added = pure2 - pure1
        raw_removed = pure1 - pure2

        def bnode_closure(graph, node):
            triples = set()
            stack = [node]
            seen = set()

            while stack:
                n = stack.pop()
                if n in seen:
                    continue
                seen.add(n)

                for t in graph.triples((n, None, None)):
                    triples.add(t)
                    if isinstance(t[2], BNode):
                        stack.append(t[2])

                for t in graph.triples((None, None, n)):
                    triples.add(t)
                    if isinstance(t[0], BNode):
                        stack.append(t[0])

            return triples

        def expand_with_bnodes(graph, triples_set):
            expanded = set(triples_set)

            for (s, p, o) in list(triples_set):
                if isinstance(o, BNode):
                    expanded |= bnode_closure(graph, o)

            return expanded

        added = expand_with_bnodes(g2, raw_added)
        removed = expand_with_bnodes(g1, raw_removed)

        def find_change_iri(triple):
            s, p, o = triple

            if not isinstance(s, URIRef):
                return None

            for ax in ocg.subjects(OWL.annotatedSource, s):
                if (ax, OWL.annotatedProperty, p) not in ocg:
                    continue

                tgt = next(ocg.objects(ax, OWL.annotatedTarget), None)

                if isinstance(o, BNode) and isinstance(tgt, BNode):
                    match = False
                    try:
                        match = (
                            bnode_closure(g1, o) == bnode_closure(g1, tgt)
                            or bnode_closure(g2, o) == bnode_closure(g2, tgt)
                        )
                    except Exception:
                        match = False
                else:
                    match = (tgt == o)

                if not match:
                    continue

                for ch in ocg.objects(ax, MEMENTO.hasOntologyStateChange):
                    if (ch, MEMENTO.hasOntologyState, s2_iri) in ocg:
                        return ch

            for ch in g2.objects(s, MEMENTO.hasOntologyStateChange):
                if (ch, MEMENTO.hasOntologyState, s2_iri) in ocg:
                    return ch

            return None

        added_list = [((s, p, o), find_change_iri((s, p, o))) for (s, p, o) in added]
        removed_list = [((s, p, o), find_change_iri((s, p, o))) for (s, p, o) in removed]

        return added_list, removed_list
        
    # ================================================================
    # REVERT
    # ================================================================

    def revert_ontology(self, ontology_name, target_state, new_state_name, author, version=None):

        target_graph = self.get_ontology_state(ontology_name, target_state)

        states = self.get_ontology_states(ontology_name)
        if not states:
            raise ValueError("No available state.")

        current_state = states[-1]
        current_graph = self.get_ontology_state(ontology_name, current_state)

        pure_target = {
            (s,p,o) for (s,p,o) in target_graph
            if self.is_content_triple(s,p,o)
        }

        pure_current = {
            (s,p,o) for (s,p,o) in current_graph
            if self.is_content_triple(s,p,o)
        }

        delta = []

        # -------------------------
        # REMOVE (current - target)
        # -------------------------

        for (s,p,o) in pure_current - pure_target:
            if p == RDF.type and o == OWL.Class:
                ch = DYNDIFF.delC
            elif p == RDF.type and o in (
                OWL.ObjectProperty,
                OWL.DatatypeProperty,
                OWL.AnnotationProperty
            ):
                ch = DYNDIFF.delP
            else:
                ch = DYNDIFF.delI

            delta.append(((s,p,o), ch))

        # -------------------------
        # ADD (target - current)
        # -------------------------
        
        for (s,p,o) in pure_target:
            if (s,p,o) not in pure_current:
                if p == RDF.type and o == OWL.Class:
                    ch = DYNDIFF.addC
                elif p == RDF.type and o in (
                    OWL.ObjectProperty,
                    OWL.DatatypeProperty,
                    OWL.AnnotationProperty
                ):
                    ch = DYNDIFF.addP
                else:
                    ch = DYNDIFF.addI

                delta.append(((s,p,o), ch))

        for (s, p, o) in pure_target:
            if p == RDF.type and o == OWL.Class:
                if (s, p, o) not in pure_current:
                    delta.append(((s, RDF.type, OWL.Class), DYNDIFF.addC))

        if version is None:
            version = f"revert_to_{target_state}"

        ocg = self.store.get_context(self._ocg_iri(ontology_name))

        current_state_iri = self._state_iri(ontology_name, current_state)

        touched_subjects = {s for (s, _, _) in [t for (t, _) in delta]}

        for ch in ocg.subjects(MEMENTO.hasOntologyState, current_state_iri):

            if (ch, RDF.type, MEMENTO.DelChangeAction) not in ocg:
                continue

            for ax in ocg.subjects(MEMENTO.hasOntologyStateChange, ch):

                ent = next(ocg.objects(ax, OWL.annotatedSource), None)
                if not isinstance(ent, URIRef):
                    continue

                if ent not in touched_subjects:
                    continue

                triple = (ent, RDF.type, OWL.Class)
                if triple not in [t for (t, _) in delta]:
                    delta.append((triple, DYNDIFF.addC))

        return self.create_ontology_state(
            ontology_name=ontology_name,
            changes=delta,
            previous_state=current_state,
            state_name=new_state_name,
            author=author,
            version=version,
            bulk=False
        )

    # ================================================================
    # REMOVE
    # ================================================================

    def remove_ontology_state(self, ontology_name, state_name):

        """
        Removes only the state graph associated with a given ontology state.

        Change graphs (OCG) and provenance metadata are intentionally
        preserved to ensure historical traceability.
        """

        self.store.remove_context(self._state_graph_iri(ontology_name, state_name))
        self.store.persist()
        return True                                                                                                                                                                                              
