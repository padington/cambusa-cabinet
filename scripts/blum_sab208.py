"""Exact typed adapter for the ACIS 20800 binary records in Demos' Blum DWG.

Uses ezdxf's generic binary framing, then the same legacy entity schemas as
the SAT reader. Original bytes and record identity are retained. No version
header substitution or geometry fitting is used.
"""
from dataclasses import replace
import struct
from ezdxf.acis.sab import Decoder
from ezdxf.acis.const import Tags as T
from cq_acis.graph import SatEntityGraph
from cq_acis.sat import parse_sat_header
from cq_acis.model import RawEntity, EntityRef, AcisModel, AcisMetadata, AcisContainer, SourceSpan
from cq_acis.tokens import CountedString
import cq_acis.entities as dec
from blum_acis208 import curve, inherited_references


def parse(data, source_id='Demos extracted ACIS stream'):
    reader = Decoder(data)
    h = reader.read_header()
    assert h.version == 20800 and h.units_in_mm == 1
    data_offset = reader.index
    tags_and_units = struct.unpack('<BdBdBd', data[data_offset-27:data_offset])
    assert tags_and_units[::2] == (6,6,6)
    units, resabs, resnor = tags_and_units[1::2]
    rows, spans = [], []
    start = reader.index
    for record in reader.read_records():
        rows.append(record)
        spans.append((start, reader.index))
        start = reader.index
    assert rows[-1][0].value == 'End-of-ACIS-data'
    assert reader.index == len(data)
    date = h.creation_date.strftime('%a %b %d %H:%M:%S %Y')
    header = parse_sat_header(f'{h.version} {h.n_records} {h.n_entities} {h.flags}\n'
        f'{len(h.product_id)} {h.product_id} {len(h.acis_version)} {h.acis_version} {len(date)} {date}\n'
        f'{units:.17g} {resabs:.17g} {resnor:.17g}\n')
    records = []
    audit = []
    for index, tokens in enumerate(rows[:-1]):
        name = tokens[0].value
        assert tokens[1].tag == T.POINTER and tokens[2].tag == T.INT
        values = []
        bool_count = 0
        enum_count = 0
        for token in tokens[3:]:
            tag, v = token
            if tag == T.POINTER:
                values.append(EntityRef(v))
            elif tag in (T.LOCATION_VEC, T.DIRECTION_VEC):
                values.extend(v)
            elif tag in (T.BOOL_TRUE, T.BOOL_FALSE):
                # Binary booleans represent named choices in legacy SAT.
                word = 'F' if v else 'I'
                if name == 'face':
                    word = (('reversed', 'forward'), ('double', 'single'), ('in', 'out'))[bool_count][not v]
                elif name in ('coedge', 'tcoedge-coedge', 'edge', 'tedge-edge', 'intcurve-curve') and bool_count == 0:
                    word = 'reversed' if v else 'forward'
                elif name == 'plane-surface' and bool_count == 0:
                    word = 'reverse_v' if v else 'forward_v'
                elif name == 'cone-surface' and bool_count == 2:
                    word = 'reversed' if v else 'forward'
                elif name in ('sphere-surface', 'torus-surface') and bool_count == 0:
                    word = 'reverse_v' if v else 'forward_v'
                values.append(word)
                bool_count += 1
            elif tag == T.ENUM and name == 'intcurve-curve':
                assert v == 0 and enum_count < 2
                values.append(('full', 'open')[enum_count])
                enum_count += 1
            elif tag == T.SUBTYPE_START:
                values.append('{')
            elif tag == T.SUBTYPE_END:
                values.append('}')
            elif tag in (T.STR, T.LITERAL_STR):
                values.append(CountedString(v, len(v.encode())))
            elif tag in (T.INT, T.DOUBLE, T.ENTITY_TYPE, T.ENUM):
                values.append(v)
            else:
                raise ValueError((index, name, tag))
        lo, hi = spans[index]
        records.append(RawEntity(index, name, EntityRef(tokens[1].value), tokens[2].value,
            tuple(values), None, source=SourceSpan(source_id,lo,hi), raw_data=data[lo:hi]))
    graph = SatEntityGraph(header, tuple(records))
    for e in records:
        for reference in e.references():
            graph.resolve(reference)
    decoded = []
    with inherited_references():
        for e in records:
            if e.type_name == 'intcurve-curve':
                value = curve(e)
                audit.append(dict(index=e.index, type=e.type_name, degree=value.degree, poles=len(value.poles)))
            elif e.type_name in ('tvertex-vertex', 'tedge-edge', 'tcoedge-coedge'):
                count = 2 if e.type_name == 'tcoedge-coedge' else 1
                expected = {'tvertex-vertex':4, 'tedge-edge':10, 'tcoedge-coedge':10}[e.type_name]
                assert len(e.values) == expected
                scalars = e.values[-count:]
                if count == 1:
                    assert 0 <= float(scalars[0]) < .001
                else:
                    assert float(scalars[0]) < float(scalars[1])
                value = dec.decode_entity(graph, replace(e, type_name=e.type_name.split('-')[-1], values=e.values[:-count]))
                audit.append(dict(index=e.index, type=e.type_name, saved_scalars=list(scalars)))
            else:
                value = dec.decode_entity(graph, e)
            decoded.append(value)
    metadata = AcisMetadata(units_mm=units, resabs=resabs, resnor=resnor, container=AcisContainer.SAB,
        save_version=20800, product_id=h.product_id, modeler_version=h.acis_version,
        creation_date=str(h.creation_date), dialect='Blum Demos legacy ACIS binary 20800')
    return AcisModel(metadata, tuple(decoded)), audit
