# The Widget Handbook

A small, self-contained sample document used for smoke tests and demos.

## Chapter 1 Introduction

Widgets are small, composable units of behavior. This chapter introduces the
`Widget` class and its `assemble()` method, and explains why composability beats
inheritance for building large systems out of small parts.

## Chapter 2 Patterns

Two patterns recur throughout widget systems. The **factory** pattern centralizes
construction so call sites stay decoupled from concrete types. The **observer**
pattern notifies dependents when a widget changes. As a rule of thumb, shard a
widget registry once it exceeds roughly 100 active widgets.

## Chapter 3 Anti-patterns

Avoid the "god-widget" that accumulates unrelated responsibilities. Never block the
`assemble()` call on network IO; do the IO first and pass the result in. Prefer
explicit wiring over hidden global state.
