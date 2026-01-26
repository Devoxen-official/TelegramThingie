import inspect

class Logger:
   _instance = None
   def __new__(cls, *args, **kwargs):
       if not cls._instance:
           cls._instance = super(Logger, cls).__new__(cls)
           cls._instance.name = "App"
       return cls._instance

   def _get_caller_name(self) -> str:
       stack = inspect.stack()
       # stack[0] is _get_caller_name
       # stack[1] is the logger method (info, debug, etc.)
       # We look for the first frame that has 'self' and is not the Logger itself
       for frame_info in stack[2:]:
           frame = frame_info.frame
           if 'self' in frame.f_locals:
               instance = frame.f_locals['self']
               cls_name = instance.__class__.__name__
               if cls_name != "Logger":
                   return cls_name
           # If we reach a frame that is not a method (no 'self'),
           # we can't reliably determine a "class name", so we stop and return default.
           # This prevents picking up 'self' from much higher in the stack (like a TestRunner).
           else:
               break
       return self.name

   def debug(self, msg: str) -> None:
       print(f"[{self._get_caller_name()}] DEBUG:{msg}")
   def format_debug(self, msg: str) -> str:
       return f"[{self._get_caller_name()}] DEBUG:{msg}"
   def error(self, msg: str) -> None:
       print(f"[{self._get_caller_name()}] ERROR:{msg}")
   def format_error(self, msg: str) -> str:
       return f"[{self._get_caller_name()}] ERROR:{msg}"
   def info(self, msg: str) -> None:
       print(f"[{self._get_caller_name()}] INFO:{msg}")
   def warning(self, msg: str) -> None:
       print(f"[{self._get_caller_name()}] WARNING:{msg}")
   def format_info(self, msg: str) -> str:
       return f"[{self._get_caller_name()}] INFO:{msg}"


logger = Logger()