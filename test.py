def solution(n, c) -> int:
    res = -1
    # write your solution here
    # Plan: 1. find consectutive 1's
    ones = []  # (start, len)
    start = -1
    for i in range(0, len(n)):
        if n[i]:
            if start >= 0:
                continue
            start = i
        else:
            if start >= 0:
                ones.append((start, i - start))
                if i - start == c:
                    return 0

    return res


# R E A D M E
# DO NOT CHANGE the code below, we use it to grade your submission.
# If changed your submission will be failed automatically.
if __name__ == "__main__":
    line = "[1,1,0,1]"
    mtx = [int(num) for num in line[1:-1].split(",")]

    n = int("2")

    print(solution(mtx, n))
