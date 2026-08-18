Reserved for higher-level orchestration logic that composes multiple API calls
(e.g. multi-step checkout flows, cart-merge-on-login). Simple CRUD calls live
directly in `src/api/`; this folder is for logic that coordinates several of
them together as an app hasn't yet needed a controller/`services` layer beyond
what already lives in `src/hooks/` (e.g. `mergeGuestCartIntoBackend` in
`useCart.ts`). Kept in the tree per the project's folder convention so it's
ready to receive that logic as the app grows.
