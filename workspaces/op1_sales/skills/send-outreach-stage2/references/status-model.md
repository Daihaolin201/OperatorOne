# Lead Status and Event Model

## Lead status values
- `queued`: qualified and pending contact resolution.
- `needs_review`: low-fit lead; requires human review before eligibility.
- `ready_to_send`: direct route found (channel + target present).
- `ready_manual`: no direct target; eligible for manual dispatch bundle.
- `awaiting_contact`: no route found and manual route disabled.
- `dispatched_prepared`: direct send request generated.
- `dispatched_manual`: manual bundle item generated.
- `replied_positive`: positive reply.
- `replied_later`: not now / timing.
- `replied_objection`: objection reply.
- `replied_other`: uncategorized reply.
- `customer_converted`: conversion signal detected.
- `closed_no_interest`: rejection reply.
- `opted_out`: unsubscribe / do-not-contact.

## Dispatch eligibility
- Eligible: `ready_to_send`, `ready_manual`
- Not eligible: `needs_review`, `awaiting_contact`, `opted_out`, closed terminal states

## Event types written to `outreach_events.latest.jsonl`
- Dispatch: `dispatch_committed`, `dispatch_manual_committed`, `dispatch_suppressed`, `dispatch_skipped_cap_or_frequency`
- Replies: `reply_positive`, `reply_not_now`, `reply_objection`, `reply_unsubscribe`, `reply_rejection`, `reply_converted`, `reply_other`
