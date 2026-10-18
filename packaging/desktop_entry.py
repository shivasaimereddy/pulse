import sys
from pulse.desktop import main

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        from pulse.release_check import run
        sys.exit(run(sys.argv[2]))
    main()
