> This repo's rules, for anyone working in it: people, Claude, or another AI tool. A rule here can add or tighten a check; with cairn installed, it can't remove one cairn already runs.

tool-version python >=3.11        [blocking]
tool-version node >=20            [warning]
command "jq -V"                   [warning]
command "claude plugin validate . --strict"   [blocking]
