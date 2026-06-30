import React, { createContext, useContext, useState } from "react";

// Uygulama içi "tam sayfa egzersiz" modunu yöneten global state.
// isFullscreen true iken paneller (header + sekme bar'ı) gizler.
const FullscreenExerciseContext = createContext({
  isFullscreen: false,
  setIsFullscreen: () => {},
});

export function FullscreenExerciseProvider({ children }) {
  const [isFullscreen, setIsFullscreen] = useState(false);
  return (
    <FullscreenExerciseContext.Provider value={{ isFullscreen, setIsFullscreen }}>
      {children}
    </FullscreenExerciseContext.Provider>
  );
}

export function useFullscreenExercise() {
  return useContext(FullscreenExerciseContext);
}

export default FullscreenExerciseContext;
