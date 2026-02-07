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

IMPORT_MEMENTO  = URIRef(
    "https://raw.githubusercontent.com/dfsantamaria/Memento/main/ontologies/memento-o.owl"
)
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
# IMPORTS + HEADER STATO
# ==========================

def declare_imports_in_state_graph(state_graph: Graph, ontology_iri: URIRef):
    state_graph.add((ontology_iri, RDF.type, OWL.Ontology))
    state_graph.add((ontology_iri, OWL.imports, IMPORT_MEMENTO))
    state_graph.add((ontology_iri, OWL.imports, IMPORT_DYNDIFF))
    state_graph.add((ontology_iri, OWL.imports, IMPORT_PROVO))

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

    # Exclude blank nodes as subjects
    if isinstance(s, BNode):
        return True

    # Exclude reification machinery
    if p in (
        OWL.annotatedSource,
        OWL.annotatedProperty,
        OWL.annotatedTarget
    ):
        return True

    # Exclude axioms as entities
    if p == RDF.type and o == OWL.Axiom:
        return True

    # Exclude MEMENTO / PROV metadata
    if str(p).startswith(str(MEMENTO)) or str(p).startswith(str(PROV)):
        return True

    # Exclude ontology headers
    if p in (OWL.imports,):
        return True

    # Exclude non-semantic rdf:type assertions
    if p == RDF.type and o not in (
        OWL.Class,
        OWL.ObjectProperty,
        OWL.DatatypeProperty,
        OWL.AnnotationProperty,
        OWL.NamedIndividual
    ):
        return True

    # Exclude system-generated axiom IRIs
    if isinstance(s, URIRef) and str(s).startswith(f"{base_uri}/axiom/"):
        return True

    return False


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

        # # Load MEMENTO-O, PROV-O, DynDiffOnto ontologies into the meta
        meta = self.store.get_context(self.meta_graph_iri)

        meta.add((MEMENTO.hasOntologyStateChange, RDF.type, OWL.AnnotationProperty))
        meta.add((MEMENTO.hasOntologyState, RDF.type, OWL.AnnotationProperty))


        GITHUB_BASE = "https://raw.githubusercontent.com/dfsantamaria/Memento/main/ontologies"

        self._memento_url = f"{GITHUB_BASE}/memento-o.owl"
        self._dyndiff_url = f"{GITHUB_BASE}/DynDiffOnto.owl"
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

        def is_safe_to_copy_to_state(s, p, o):
            if p in (OWL.equivalentClass, RDFS.subClassOf):
                if isinstance(o, BNode):
                    return False
            return True

        # HEADER AND IMPORTS
        declare_imports_in_state_graph(state_graph, ontology_iri)
        for pfx, ns in [
            ("rdf", RDF), ("rdfs", RDFS), ("owl", OWL), ("xsd", XSD),
            ("memento", MEMENTO), ("prov", PROV), ("dyn", DYNDIFF)
        ]:
            state_graph.bind(pfx, ns)

        declare_version_dataprops(state_graph)

        ANNOTATION_PROPS = {
            RDFS.comment, RDFS.label,
            OWL.versionInfo, OWL.priorVersion,
            OWL.backwardCompatibleWith, OWL.incompatibleWith
        }

        filtered = []
        for (s, p, o) in set(g_in):
            if p == RDF.type and o == OWL.Ontology:
                continue
            if p == OWL.imports:
                continue
            if p not in ANNOTATION_PROPS:
                filtered.append((s, p, o))

            if p not in (RDFS.comment,):
                if is_safe_to_copy_to_state(s, p, o):
                    if p == RDF.type and o == OWL.NamedIndividual:
                        if (
                            (s, RDF.type, OWL.Class) in g_in or
                            (s, RDF.type, OWL.ObjectProperty) in g_in or
                            (s, RDF.type, OWL.DatatypeProperty) in g_in
                        ):
                            continue
                    state_graph.add((s, p, o))

        ts = iso_timestamp()
        ts_lit = Literal(ts, datatype=XSD.dateTime)

        # --------------------------
        # FILTER VALID CHANGES
        # --------------------------

        ANNOTATION_PROPS = {
            RDFS.comment, RDFS.label,
            OWL.versionInfo, OWL.priorVersion,
            OWL.backwardCompatibleWith, OWL.incompatibleWith
        }

        SYSTEM_PREDS = {
            OWL.annotatedSource,
            OWL.annotatedProperty,
            OWL.annotatedTarget,
            MEMENTO.hasOntologyState,
            MEMENTO.hasOntologyStateChange,
            OWL.imports,
            RDF.type
        }

        entity_to_change = {}
        ent_seq = 0

        for (s, p, o) in filtered:
            if is_system_triple(s, p, o, self.base):
                continue
            if p in ANNOTATION_PROPS:
                continue

            if not (
                (s, RDF.type, OWL.Class) in g_in or
                (s, RDF.type, OWL.ObjectProperty) in g_in or
                (s, RDF.type, OWL.DatatypeProperty) in g_in or
                (s, RDF.type, OWL.AnnotationProperty) in g_in or
                (s, RDF.type, OWL.NamedIndividual) in g_in
            ):
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
            ocg.add((ch_iri, RDF.type, MEMENTO.OntologyStateChange))
            ocg.add((ch_iri, RDF.type, change_action_class(ch_type)))
            ocg.add((ch_iri, MEMENTO.hasOntologyState, state_iri))

            # STATE GRAPH
            state_graph.add((ch_iri, RDF.type, MEMENTO.OntologyStateChange))
            state_graph.add((ch_iri, RDF.type, change_action_class(ch_type)))
            state_graph.add((ch_iri, MEMENTO.hasOntologyState, state_iri))

            state_graph.set((ent, MEMENTO.hasOntologyStateChange, ch_iri))

        # --------------------------
        # REIFICATION TBOX AXIOMS (equivalentClass, subClassOf, ecc.)
        # con state and change annotations
        # --------------------------

        for (s, p, o) in filtered:
            if p not in (
                OWL.equivalentClass,
                RDFS.subClassOf,
                OWL.equivalentProperty,
                RDFS.subPropertyOf,
                RDFS.domain,
                RDFS.range
            ):
                continue

            if isinstance(o, BNode):
                continue

            axiom_iri = make_axiom_iri(self.base, ontology_name)

            ocg.add((axiom_iri, RDF.type, OWL.Axiom))
            ocg.add((axiom_iri, OWL.annotatedSource, s))
            ocg.add((axiom_iri, OWL.annotatedProperty, p))
            ocg.add((axiom_iri, OWL.annotatedTarget, o))

            ocg.add((axiom_iri, MEMENTO.hasOntologyState, state_iri))

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

        # version parsing
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

        # mirror into state graph
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
        state_name: str,
        author: str,
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

        # --------------------------
        # FILTER VALID CHANGES 
        # --------------------------

        changes = [
            ((s, p, o), t)
            for ((s, p, o), t) in changes
            if not is_system_triple(s, p, o, self.base)
        ]

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

            for (s, p, o) in set(prev_ctx):

                if (s, RDF.type, OWL.Axiom) in prev_ctx:
                    continue

                if p in (
                    OWL.annotatedSource,
                    OWL.annotatedProperty,
                    OWL.annotatedTarget
                ):
                    continue

                if isinstance(s, BNode):
                    continue

                new_state_graph.add((s, p, o))

        # --------------------------
        # COPY hasOntologyStateChange FROM PREVIOUS STATE
        # --------------------------

        if prev_state_name:
            prev_ctx = self.get_ontology_state(ontology_name, prev_state_name)

            for (ent, _, old_change) in prev_ctx.triples(
                (None, MEMENTO.hasOntologyStateChange, None)
            ):
                if not isinstance(ent, URIRef):
                    continue

                new_state_graph.add(
                    (ent, MEMENTO.hasOntologyStateChange, old_change)
                )

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

        meta.add((version_iri, RDF.type, MEMENTO.OntologyStateVersion))

        meta.add((agent_iri, RDF.type, PROV.Agent))
        meta.add((agent_iri, RDF.type, PROV.Person))

        # mirror
        new_state_graph.add((new_state_iri, RDF.type, MEMENTO.OntologyState))
        new_state_graph.add((new_state_iri, PROV.startedAtTime, ts_literal))
        new_state_graph.add((new_state_iri, MEMENTO.hasOntologyStateVersion, version_iri))
        new_state_graph.add((new_state_iri, PROV.wasGeneratedBy, agent_iri))

        # mirror version info into state graph
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

        for (s, p, o), ch_type in changes:
            if not isinstance(s, URIRef):
                continue

            if DYNDIFF.addC == ch_type:
                if (s, RDF.type, OWL.Class) not in new_state_graph:
                    new_state_graph.add((s, RDF.type, OWL.Class))

            if DYNDIFF.addI == ch_type:
                if (s, p, o) not in new_state_graph:
                    new_state_graph.add((s, p, o))

            elif DYNDIFF.delC == ch_type:
                for triple in list(new_state_graph.triples((s, None, None))):
                    _, pred, obj = triple

                    if pred in (
                        MEMENTO.hasOntologyStateChange,
                        RDF.type,
                        RDFS.label,
                        RDFS.comment
                    ):
                        continue

                    new_state_graph.remove(triple)

        # --------------------------
        #  DELTA + AXIOMS
        # (1 OntologyStateChange X CHANGE TYPE)
        # (1 OntologyStateChange X ENTITY)
        # --------------------------

        entity_to_change = {}
        bulk_change_for_type = {}
        change_seq = 0

        for (s, p, o), ch_type in changes:
            if not isinstance(s, URIRef):
                continue
            
            if bulk:
                if ch_type not in bulk_change_for_type:
                    change_seq += 1
                    ch_iri = make_change_iri(
                        self.base, ontology_name, ts, state_name, change_seq
                    )
                    bulk_change_for_type[ch_type] = ch_iri

                    # OCG
                    ocg.add((ch_iri, RDF.type, MEMENTO.OntologyStateChange))
                    ocg.add((ch_iri, RDF.type, change_action_class(ch_type)))
                    ocg.add((ch_iri, MEMENTO.hasOntologyState, new_state_iri))

                    # STATE GRAPH
                    new_state_graph.add((ch_iri, RDF.type, MEMENTO.OntologyStateChange))
                    new_state_graph.add((ch_iri, RDF.type, change_action_class(ch_type)))
                    new_state_graph.add((ch_iri, MEMENTO.hasOntologyState, new_state_iri))

                entity_to_change[s] = bulk_change_for_type[ch_type]

            else: 

                if ch_type in (DYNDIFF.addC, DYNDIFF.addP, DYNDIFF.addI):
                    if not (
                        (s, RDF.type, OWL.Class) in new_state_graph or
                        (s, RDF.type, OWL.ObjectProperty) in new_state_graph or
                        (s, RDF.type, OWL.DatatypeProperty) in new_state_graph or
                        (s, RDF.type, OWL.AnnotationProperty) in new_state_graph or
                        (s, RDF.type, OWL.NamedIndividual) in new_state_graph
                    ):
                        continue

                if s not in entity_to_change:
                    change_seq += 1
                    ch_iri = make_change_iri(
                        self.base, ontology_name, ts, state_name, change_seq
                    )
                    entity_to_change[s] = ch_iri

                    # OCG
                    ocg.add((ch_iri, RDF.type, MEMENTO.OntologyStateChange))
                    ocg.add((ch_iri, RDF.type, change_action_class(ch_type)))
                    ocg.add((ch_iri, MEMENTO.hasOntologyState, new_state_iri))

                    # STATE GRAPH
                    new_state_graph.add((ch_iri, RDF.type, MEMENTO.OntologyStateChange))
                    new_state_graph.add((ch_iri, RDF.type, change_action_class(ch_type)))
                    new_state_graph.add((ch_iri, MEMENTO.hasOntologyState, new_state_iri))

        for (s, p, o), ch_type in changes:
            if not isinstance(s, URIRef):
                continue

            if (p, RDF.type, OWL.AnnotationProperty) in self.store.get_context(self.meta_graph_iri):
                continue

            if s not in entity_to_change:
                continue

            ch_iri = entity_to_change[s]
            axiom_iri = make_axiom_iri(self.base, ontology_name)

            ocg.add((axiom_iri, RDF.type, OWL.Axiom))
            ocg.add((axiom_iri, OWL.annotatedSource, s))
            ocg.add((axiom_iri, OWL.annotatedProperty, p))
            ocg.add((axiom_iri, OWL.annotatedTarget, o))
            ocg.add((axiom_iri, MEMENTO.hasOntologyStateChange, ch_iri))
            ocg.add((axiom_iri, MEMENTO.hasOntologyState, new_state_iri))

            new_state_graph.add((axiom_iri, RDF.type, OWL.Axiom))
            new_state_graph.add((axiom_iri, OWL.annotatedSource, s))
            new_state_graph.add((axiom_iri, OWL.annotatedProperty, p))
            new_state_graph.add((axiom_iri, OWL.annotatedTarget, o))
            new_state_graph.add((axiom_iri, MEMENTO.hasOntologyStateChange, ch_iri))
            new_state_graph.add((axiom_iri, MEMENTO.hasOntologyState, new_state_iri))

        for ent, ch_iri in entity_to_change.items():
            new_state_graph.add((ent, MEMENTO.hasOntologyStateChange, ch_iri))

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

        if p == RDF.type and o in (
            MEMENTO.OntologyState,
            MEMENTO.OntologyStateVersion,
            PROV.Agent,
            PROV.Person
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

        s1_iri = self._state_iri(ontology_name, state1)
        s2_iri = self._state_iri(ontology_name, state2)

        pure1 = set(
            (s, p, o)
            for (s, p, o) in g1
            if self.is_content_triple(s, p, o)
        )

        pure2 = set(
            (s, p, o)
            for (s, p, o) in g2
            if self.is_content_triple(s, p, o)
        )

        added = pure2 - pure1
        removed = pure1 - pure2

        def find_type(triple, state_iri):
            (s, p, o) = triple
            for ax in ocg.subjects(OWL.annotatedSource, s):
                if (ax, OWL.annotatedProperty, p) not in ocg: continue
                if (ax, OWL.annotatedTarget, o) not in ocg: continue
                if (ax, MEMENTO.hasOntologyState, state_iri) not in ocg: continue
                for ch in ocg.objects(ax, MEMENTO.hasOntologyStateChange):
                    for t in ocg.objects(ch, RDF.type):
                        if t in (MEMENTO.AddChangeAction, MEMENTO.DelChangeAction):
                            return t
            return None

        added_list = [(t, find_type(t, s2_iri)) for t in added]
        removed_list = [(t, find_type(t, s1_iri)) for t in removed]

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
        for (s,p,o) in pure_target - pure_current:
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

        if version is None:
            version = f"revert_to_{target_state}"

        return self.create_ontology_state(
            ontology_name,
            delta,
            new_state_name,
            author,
            version=version,
            prev_state_name=current_state
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
