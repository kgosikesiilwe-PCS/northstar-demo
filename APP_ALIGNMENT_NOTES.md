# NorthStar MVP Alignment Notes

## Current alignment

The current code is now Medicare-aligned rather than a generic care-vault MVP. The app centers around:

- Medicare & insurance profile
- PCP / doctors / providers
- Medications and allergies
- Medicare advisor / agent-of-record information supplied by the beneficiary
- Family-only authorization
- Medicare Review Packet
- Emergency Card
- Audit logs and sensitive-data warnings

## Important MVP assumption

Advisor/AOR and PCP details are beneficiary-provided in the MVP. The app should display this as beneficiary-confirmed information, not carrier-verified information.

## Future agent subscription path

The present MVP does not give agents access. A future agent subscription module should add:

- Agent accounts and agency accounts
- NPN/license capture
- Beneficiary authorization for agent access
- Separate agent consent scopes
- Client list for agents
- Annual review workflow
- Scope of Appointment workflow, if used for Medicare marketing/sales conversations
- Subscription billing
- Carrier/AOR verification status fields
- Stronger admin access controls and production-grade MFA

The safer commercial framing is: agents pay for a compliant client-service workspace for beneficiaries who explicitly authorize them, not for access to patient data.
