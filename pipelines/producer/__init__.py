"""Nerra Producer: the network's back office (September 2026).

The Producer is never on-air. Its first job, ``inbox``, reads Patrick's
Gmail inbox through a delegated service account, classifies each thread
with Grok, and answers clean guest pitches in-thread with the apply link
for the right Mira-hosted interview show (The Age of AI or Nerra Voices).
Everything it is unsure about becomes a draft plus a Slack note; every
decision is logged to ``producer_runs``.

Modules: ``gmail_client`` (all Gmail network code), ``classify`` (prompt +
strict JSON schema), ``policy`` (mode + hard exclusions from
``shows/_producer_policy.yaml``), ``inbox`` (the entry point).
"""
