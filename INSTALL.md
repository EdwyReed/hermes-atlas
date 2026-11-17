# Installation and reversible migration

Select the intended profile explicitly with `HERMES_HOME`. Do not copy another
profile's credentials, config, sessions or personal guidance. Examples below use
operator-selected paths; none are runtime bindings shipped with the package.

## New installation

Authenticate Git access to the private repository using the operator's existing
GitHub setup. Resolve and review the release's immutable 40-character commit SHA,
then install disabled:

```bash
export HERMES_HOME=/absolute/selected/profile
export REV=REPLACE_WITH_REVIEWED_40_CHARACTER_COMMIT
hermes plugins install https://github.com/EdwyReed/hermes-atlas.git --ref "$REV" --no-enable
```

The dependency consent prompt is intentional. Use `--yes-deps` only when the
operator has approved dependency preparation. Check the installer output, not
only its exit code. Alternatively, a reviewed local checkout can be linked as
`$HERMES_HOME/plugins/atlas` and enabled through the native CLI; keep that checkout
pinned and do not install a second copy of the same plugin.

Configure settings with the supported CLI (never edit YAML by hand):

```bash
hermes config set --force plugins.entries.atlas.settings.atlas_engine '{"endpoint":"https://atlas.example.invalid","token_file":"/absolute/selected/profile/credentials/atlas.token","timeout_seconds":45}'
hermes plugins enable atlas
```

Replace the example endpoint/path with this profile's **existing authorized**
binding. `token_file` contains only the bearer token and must be readable by the
runtime; do not commit it or print it. For an existing environment-managed secret,
use `token_env` naming that variable instead. Endpoint, timeout, allowlist and
credential references are settings; secret values stay outside config.yaml.
Optional `allowed_operations` is an array of exact operation names. No endpoint
or credential is inferred from an old media adapter or MCP proxy.

Without an authorized binding, enable the plugin with empty settings for skill
access only. Do not fabricate a credential to make tool availability pass.
Do not run this new-install route over active legacy tool names: use migration.

## Existing profiles: plan, review, apply

`rollout.py` operates on one explicitly selected existing home. It links the
shared reviewed checkout, retires only the listed legacy entries, preserves
private recipes, and uses `hermes config set` with exact config readback. It does
not touch MCP servers, unrelated plugin settings, model/memory configuration,
credentials or services. Run as the profile's authorized operator.

```bash
export PACKAGE=/absolute/reviewed/hermes-atlas
export TARGET_HOME=/absolute/selected/profile
export RECEIPT=/absolute/private/maintenance/selected-atlas.json
python "$PACKAGE/rollout.py" plan --home "$TARGET_HOME" --receipt "$RECEIPT"
# Review this receipt locally. It contains private settings and source references.
python "$PACKAGE/rollout.py" apply --receipt "$RECEIPT"
```

Keep receipts and backups outside the repository in an operator-private directory
(mode 0700). Receipts are written mode 0600. Planning changes no profile, but
writes a private plan. Never paste the complete receipt into a public issue.
Config/entry fingerprints must still match at apply time; re-plan if stale.
Do not run competing profile edits while applying or rolling back.

The exact retirement lists are in `LEGACY_PLUGINS` and `ABSORB` in `rollout.py`.
The temporary `anime_mosaic` alias avoids a second backend. Absorbed skills become
private references at:

```text
$HERMES_HOME/plugin-data/atlas/references/profile-guidance/INDEX.md
```

Original attribution and recipe bytes are preserved; retired execution routes
are historical evidence only. The migration rewrites exact backtick references
to absorbed skill names, but leaves shared symlinked consumer skills untouched
and reports them for owner review. Specialist maintenance skills and `danbooru`
are not absorbed.

Only a currently enabled native `atlas-engine-client` binding is carried forward.
Missing/disabled native bindings produce guidance-only mode and retain existing
MCP access unchanged. That is a successful no-access-expansion migration, not
proof of a working Engine connection. Review old broken media bindings separately;
never import them automatically as credentials for the new client.

## Verify and activate

After an authorized apply, inspect the profile's exact plugin settings locally,
then verify in a fresh process:

```bash
HERMES_HOME="$TARGET_HOME" hermes plugins doctor "$PACKAGE" --ci
HERMES_HOME="$TARGET_HOME" python "$PACKAGE/tests/native_probe.py" --package "$PACKAGE" --tools-available yes
```

Use `--tools-available no` for guidance-only profiles. The Python interpreter must
have Hermes importable, as for the unit suite. The native probe reads only the
selected home's plugin/skill registry and denies sockets during registration.
`yes` checks binding presence, not credential validity or network connectivity.
It is not a live gateway probe. Also inspect normal native skill listing for
legacy duplicates/shared references reported by the plan.

At a separately approved activation boundary, load `atlas:atlas` in the actual
surface. Read capabilities and schema through this profile's existing binding;
for read-only proxy profiles retain that proxy. Do not infer live activation
from fresh-process discovery. Do not restart an occupied gateway without approval.
No inference, upload, model download or native write belongs in installation
acceptance unless separately requested.

## Roll back

```bash
python "$PACKAGE/rollout.py" rollback --receipt "$RECEIPT"
```

Rollback accepts an applied or interrupted partial migration. It restores the
recorded plugin settings, old entries and edited skill references, removes its
Atlas link, and moves preserved guidance into the private backup. It refuses to
clobber externally changed plugin settings, links, references or recreated legacy
paths. For such a refusal, reconcile the reported conflict; do not force-delete
anything. Receipts remain private maintenance evidence. If the original config
had no `plugins` key, rollback restores its logical empty value rather than
byte-identical YAML/key absence. Config formatting is not preserved.

Apply/rollback, stale-plan refusal, interrupted apply, shared-reference handling,
credential isolation and guidance-only native discovery are exercised in temporary
profiles by `tests/test_rollout.py`. No live rollout is implied by these checks.
