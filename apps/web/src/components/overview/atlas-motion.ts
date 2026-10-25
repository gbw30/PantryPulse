import "./supply-flow.css";

/** The design lab's spring (PP-52 decision 3), shared by markers, drag settle, panels and press feedback. */
export const SPRING = { type: "spring", stiffness: 250, damping: 22 } as const;

/** Press feedback for chips and buttons (a transform, so MotionConfig reducedMotion="user" skips it). */
export const PRESS = { whileTap: { scale: 0.96 }, transition: SPRING } as const;
