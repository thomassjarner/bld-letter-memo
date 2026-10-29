"""Algorithms supplied for the Method Library; preserve original labels/text.

The catalog verifies cube effects rather than trusting the position labels or
the supplied commutator column. The final four entries use a UFL buffer.
"""

# (stated cycle, expanded algorithm, commutator as supplied)
SUPPLIED_ALGORITHMS = (
    ('UFR-UBL-LUF', "f U2 R' D' R U2 R' D R f'", "f:[U2,R' D' R]"),
    ('UFR-UBL-FDL', "U' D' R D' R' U2 R D R' U' D", "U' D':[R D' R',U2]"),
    ('UFR-UBL-RUB', "R' U D R2 U' R' D' R U R' D R' U' D' R", "R' U D R:[R U' R',D']"),
    ('UFR-UBR-LUF', "R2 D' R U' R' D R U R", "R':[R' D' R,U']"),
    ('UFR-UBR-LDB', "U' R D' R' U R D R'", "[U',R D' R']"),
    ('UFR-UFL-FDR', "D' R' D R U' R' D' R U D", "D':[R' D R,U']"),
    ('UFR-LUB-LUF', "L U' R' U L' U' R U", "[L,U' R' U]"),
    ('UFR-LUB-DFR', "D2 R2 D' R' U R D R' U' R' D2", "D2 R:[R D' R',U]"),
    ('UFR-LDB-UFL', "U2 R D' R' U R D R' U", "U':[U',R D' R']"),
    ('UFR-LDB-FUL', "D R U' R' D R U2 R' D' R U' R' D'", "D R U':[R' D R,U2]"),
    ('UFR-LDF-RDB', "U' D2 R' U' R D2 R' U R U", "U':[D2,R' U' R]"),
    ('UFR-FUL-LDB', "R U D R' D R U2 R' D' R U D' R'", "R U D:[R' D R,U2]"),
    ('UFR-FUL-BUL', "R U R' U D R D R' U2 R D' R' U D' R U' R'", "R U R' U D:[R D R',U2]"),
    ('UFR-FDL-LDB', "D R U R' D R U' R' D2", "D:[R U R',D]"),
    ('UFR-FDL-BDL', "D' R D' R' U' R D2 R' U R D' R' D", "D' R D':[R' U' R,D2]"),
    ('UFR-FDR-FDL', "U R U' D R' D' R U R' D R D' R' U'", "U R D:[U',R' D' R]"),
    ('UFR-FDR-DBR', "U R U' D' R' D R U R' D' R D R' U'", "U R D':[U',R' D R]"),
    ('UFR-RUB-RDB', "U R U' R' D' R U2 R' D R U' R' U'", "U R U':[R' D' R,U2]"),
    ('UFR-RDB-LUF', "R' U R' D' R U2 R' D R U R", "R' U:[R' D' R,U2]"),
    ('UFR-RDB-DFL', "U' R2 D R U R' D' R U' R U", "U' R':[R' D R,U]"),
    ('UFR-BUR-UBL', "R' D' R' D R U2 R' D' R U2 D R", "R' D':[R' D R,U2]"),
    ('UFR-BUL-UBR', "R' U2 R' D' R U2 R' D R2", "R':[U2,R' D' R]"),
    ('UFR-BUL-BDL', "U' R' U' R D' R' U' R D R' U2 R U", "U' R' U':[R D' R',U']"),
    ('UFR-BUL-DFL', "U' R2 D R U' R' D' R U R U", "U' R':[R' D R,U']"),
    ('UFR-BDR-BUL', "D' R' D R' U R D' R' U' R2 D", "D' R':[D,R' U R]"),
    ('UFR-BDL-BUR', "D R' U R U' R' D R U R' U' D' R D'", "D R' U:[R U' R',D]"),
    ('UFR-DFL-BDR', "D' R U' R D' R' U R D R2 D", "D' R:[U',R D' R']"),
    ('UFR-DFR-UFL', "U' R' D R U' R D' R' U R D R' U R' D' R", "[U',R' D R U' R D' R']"),
    ('UFR-DFR-LDB', "D2 R U' R D' R' U R D R2 D2", "D2 R:[U',R D' R']"),
    ('UFR-DFR-FDL', "R U' R' U2 R' D R U2 R' D' R2 U R'", "R U' R':[U2,R' D R]"),
    ('UFR-DFR-BDR', "D' R D R' D' R U R' D R U' D' R' D", "D' R D:[R' D' R,U]"),
    ('UFR-DBL-LUF', "R2 D' R U' R' D' R U R' D2 R2", "R2 D':[R U' R',D']"),
    ('UFR-DBL-DFL', "R U' D' R' U R D' R' U' R U D2 R'", "R U' D':[R' U R,D']"),
    ('UFR-DBR-LUF', "R U' R2 U R D R' U' R D' R U R'", "R U' R':[R' U R,D]"),
    ('UFL-LUB-RDF', "U R' U R D R' U2 R D' R' U R U'", "U R' U:[R D R',U2]"),
    ('UFL-LDF-RDB', "D R U' R' D2 R U R' D", "D:[R U' R',D2]"),
    ('UFL-RUB-DBL', "D' R D' R U' R' D R U R2 D", "D' R:[D',R U' R']"),
    ('UFL-BDR-RUB', "U' D' R' D R' U R D' R' U' R2 U D", "U' D' R':[D,R' U R]"),
)
