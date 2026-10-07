"""Frozen entry point; packaging checks never create windows or touch Bluetooth."""
import sys

if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--self-test':
        from mr3_packaging_check import run
        raise SystemExit(run(sys.argv[2]))
    from mr3_app import main
    main()
