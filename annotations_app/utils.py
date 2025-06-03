# annotations_app/utils.py
from Bio import PDB

def extract_pdb_sequence(pdb_path: str) -> str:
    """
    Return the concatenated 1-letter amino-acid sequence contained
    in *pdb_path*.  Empty string if nothing could be parsed.
    """
    parser = PDB.PDBParser(QUIET=True)
    structure = parser.get_structure("struct", pdb_path)
    ppb = PDB.PPBuilder()
    seqs = [pp.get_sequence() for pp in ppb.build_peptides(structure)]
    return "".join(str(s) for s in seqs)
