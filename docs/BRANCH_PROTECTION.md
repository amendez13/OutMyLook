# Branch Protection Configuration

This document describes the branch protection rules configured for the `main` branch to ensure code quality and prevent accidental or harmful changes.

## Quick Start

**To apply branch protection, choose one option:**

### Option A: Automated Setup (Recommended)
```bash
./scripts/github/setup-branch-protection.sh
```

### Option B: GitHub CLI One-Liner
```bash
gh api -X PUT /repos/your-username/OutMyLook/branches/main/protection \
  --input scripts/github/branch-protection-config.json
```

### Option C: Manual Setup
See [Manual Configuration via GitHub UI](#option-2-manual-configuration-via-github-ui) below.

## Overview

Branch protection rules help maintain code quality by requiring specific checks to pass before code can be merged into the `main` branch. This ensures that all changes are reviewed, tested, and meet quality standards.

## Protection Rules for `main` Branch

### Required Status Checks

All CI checks must pass before merging:

**Strict Status Checks:**
- `Lint and Code Quality` - Code formatting, linting, and type checking
- `Test Python 3.10` - Tests on Python 3.10
- `Test Python 3.11` - Tests on Python 3.11
- `Test Python 3.12` - Tests on Python 3.12
- `Validate Configuration` - Configuration file validation
- `CI Status Check` - Final CI status verification

**Non-blocking Checks:**
- `Security Checks` - Security scans (warnings allowed)
- `Integration Tests` - Integration tests (when enabled)

**Configuration:**
- **Require branches to be up to date before merging**: Enabled
  - This ensures that PRs are tested against the latest `main` before merging
  - Prevents "green build, broken main" scenarios

### Pull Request Requirements

**Require Pull Request Reviews:**
- Disabled for solo development
  - GitHub doesn't allow PR authors to approve their own PRs
  - For solo developers: Protection still ensures CI passes and conversations are resolved
  - Can be enabled when working with a team by setting `required_approving_review_count`

**Note for Solo Developers:**
- While PR approval is disabled, you still benefit from:
  - Required status checks (all CI must pass)
  - Conversation resolution requirement
  - Linear history enforcement
  - Protection against accidental force pushes/deletions

### Additional Protections

| Setting | Status | Description |
|---------|--------|-------------|
| Require linear history | Enabled | Prevents merge commits, keeps history clean |
| Allow force pushes | Disabled | Prevents accidentally overwriting history |
| Allow deletions | Disabled | Prevents accidental branch deletion |
| Require conversation resolution | Enabled | All comments must be resolved |
| Include administrators | Enabled | Admins must also follow rules |

## Implementation

### Option 1: Using GitHub CLI (Recommended)

Run this command to apply the branch protection configuration:

```bash
gh api -X PUT /repos/your-username/OutMyLook/branches/main/protection \
  --input scripts/github/branch-protection-config.json
```

The configuration file is located at `scripts/github/branch-protection-config.json`.

### Option 2: Manual Configuration via GitHub UI

1. Go to the repository on GitHub
2. Click **Settings** → **Branches**
3. Under "Branch protection rules", click **Add rule**
4. Enter branch name pattern: `main`
5. Configure the following settings:

**Protect matching branches:**
- [ ] Require a pull request before merging (optional for solo dev)
- [x] Require status checks to pass before merging
  - [x] Require branches to be up to date before merging
  - Add these status checks:
    - `Lint and Code Quality`
    - `Test Python 3.10`
    - `Test Python 3.11`
    - `Test Python 3.12`
    - `Validate Configuration`
    - `CI Status Check`
- [x] Require conversation resolution before merging
- [x] Require linear history
- [x] Include administrators

6. Click **Create** or **Save changes**

## Working with Branch Protection

### For Pull Requests

When you create a pull request:

1. **CI checks will run automatically**
   - All required checks must pass
   - Fix any failures before merging

2. **Merge when ready**
   - All checks must be green
   - All conversations resolved
   - Branch is up to date with `main`

### Merge Strategies

**Recommended: Squash and Merge**
- Combines all PR commits into a single commit
- Keeps `main` history clean and readable

**Alternative: Rebase and Merge**
- Replays PR commits on top of `main`
- Maintains individual commit history

**Not Recommended: Merge Commit**
- Disabled by "Require linear history" setting

### Handling Merge Conflicts

If your PR conflicts with `main`:

```bash
git checkout your-branch
git fetch origin
git rebase origin/main
# Resolve conflicts
git add <resolved-files>
git rebase --continue
git push --force-with-lease origin your-branch
```

## Troubleshooting

### "Required status check is expected but not reported"

**Cause:** The status check name doesn't match the job name in CI.

**Solution:**
1. Check the exact status check name in a recent PR
2. Update branch protection to use the exact name

### Can't merge even though CI passes

**Possible causes:**
1. Unresolved conversations → Resolve all comments
2. Branch not up to date → Rebase on `main`
3. Status check name mismatch → Check exact names

## Security Considerations

**What branch protection protects against:**
- Accidental pushes to `main`
- Merging broken code
- Force pushing over history
- Deleting the main branch

**Additional security measures:**
- Enable GitHub's secret scanning
- Use signed commits for critical changes
- Regularly rotate access tokens and secrets

## Best Practices

1. **Always work in feature branches**
   - Never commit directly to `main`
   - Use descriptive branch names: `feature/add-dark-mode`, `fix/auth-bug`

2. **Keep PRs focused and small**
   - Easier to review
   - Faster to merge
   - Less likely to conflict

3. **Keep your branch up to date**
   - Regularly rebase on `main`
   - Avoid long-lived feature branches

## References

- [GitHub Branch Protection Documentation](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
- [GitHub Required Status Checks](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches#require-status-checks-before-merging)
